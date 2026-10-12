"""OIDC sign-in rules: settings, discovery, the authorization-code flow and identity links.

Views call these. Nothing here creates an account on its own (ADR 0006).
HTTP goes through httpx. Tests set `HTTP_TRANSPORT` to a fake provider.
"""
import hmac
import logging
import os
import secrets
import time
from urllib.parse import urlparse

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.urls import reverse
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from accounts.services import record_audit

from . import crypto
from .models import OIDCIdentity, OIDCSettings

log = logging.getLogger(__name__)

HTTP_TRANSPORT = None  # tests only
HTTP_TIMEOUT = 5.0
DISCOVERY_TTL = 300
FLOW_MAX_AGE = 600
SESSION_KEY = "oidc_flow"
INVITE_KEY = "invite_token"
ID_TOKEN_ALGS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256", "PS384", "PS512"]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class OIDCError(Exception):
    """A failed OIDC step. The message is safe to show to the user."""


# Settings ---------------------------------------------------------------------------


def _env_bool(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_settings():
    """Return the single settings row. The first access pre-fills it from OIDC_* variables."""
    row = OIDCSettings.objects.filter(pk=1).first()
    if row:
        return row
    row = OIDCSettings(
        pk=1,
        issuer_url=os.environ.get("OIDC_ISSUER_URL", "").strip(),
        client_id=os.environ.get("OIDC_CLIENT_ID", "").strip(),
        client_secret_encrypted=crypto.encrypt(os.environ.get("OIDC_CLIENT_SECRET", "")),
    )
    row.enabled = _env_bool("OIDC_ENABLED") and bool(row.issuer_url and row.client_id and row.client_secret_encrypted)
    try:
        with transaction.atomic():
            row.save(force_insert=True)
    except IntegrityError:
        row = OIDCSettings.objects.get(pk=1)
    return row


def secret_is_usable(row):
    return crypto.decrypt(row.client_secret_encrypted) is not None


def is_configured(row):
    return bool(row.issuer_url and row.client_id and secret_is_usable(row))


def is_available():
    row = get_settings()
    return row.enabled and is_configured(row)


def issuer_problem(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "Enter a full URL, such as https://auth.example.com/application/o/merit-badge/."
    if parsed.scheme != "https" and parsed.hostname not in LOCAL_HOSTS:
        return "The issuer URL must start with https:// (http:// is allowed only for localhost)."
    return ""


def save_settings(actor, cleaned):
    row = get_settings()
    changed = []
    for field in ("enabled", "issuer_url", "client_id", "scopes", "button_label"):
        if getattr(row, field) != cleaned[field]:
            setattr(row, field, cleaned[field])
            changed.append(field)
    if cleaned.get("client_secret"):
        row.client_secret_encrypted = crypto.encrypt(cleaned["client_secret"])
        changed.append("client_secret")
    if changed:
        row.updated_by = actor
        row.save()
        cache.delete(_cache_key(row.issuer_url))
        record_audit("oidc_settings_changed", actor, None, fields=changed)
    return row


def callback_uri(request):
    return request.build_absolute_uri(reverse("oidc_callback"))


# Discovery --------------------------------------------------------------------------


def _client_kwargs():
    kw = {"timeout": HTTP_TIMEOUT}
    if HTTP_TRANSPORT is not None:
        kw["transport"] = HTTP_TRANSPORT
    return kw


def _cache_key(issuer):
    return "oidc-discovery:" + (issuer or "").rstrip("/")


def _get_json(url):
    problem = issuer_problem(url)
    if problem:
        raise OIDCError("The provider returned an address that is not allowed.")
    try:
        with httpx.Client(follow_redirects=False, **_client_kwargs()) as http:
            resp = http.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("OIDC request failed: %s", type(exc).__name__)
        raise OIDCError("The provider did not answer correctly. Check the issuer URL and try again.")


def discover(issuer, use_cache=True):
    issuer = (issuer or "").strip()
    problem = issuer_problem(issuer) if issuer else "No issuer URL is set."
    if problem:
        raise OIDCError(problem)
    key = _cache_key(issuer)
    if use_cache:
        doc = cache.get(key)
        if doc:
            return doc
    doc = _get_json(issuer.rstrip("/") + "/.well-known/openid-configuration")
    if not isinstance(doc, dict):
        raise OIDCError("The discovery document is not valid.")
    if str(doc.get("issuer", "")).rstrip("/") != issuer.rstrip("/"):
        raise OIDCError("The issuer in the discovery document does not match the issuer URL.")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not doc.get(name):
            raise OIDCError(f"The discovery document has no {name}.")
        if issuer_problem(doc[name]):
            raise OIDCError(f"The {name} is not an allowed address.")
    cache.set(key, doc, DISCOVERY_TTL)
    return doc


def test_discovery(row):
    """Return (ok, message). The message never holds a secret."""
    try:
        doc = discover(row.issuer_url, use_cache=False)
    except OIDCError as exc:
        return False, str(exc)
    return True, f"Discovery works. Issuer: {doc['issuer']}."


# Flow -------------------------------------------------------------------------------


def begin_flow(request, mode):
    """Return the provider URL to send the browser to. Stores state, nonce and verifier in the session."""
    row = get_settings()
    if not (row.enabled and is_configured(row)):
        raise OIDCError("OIDC sign-in is not available.")
    doc = discover(row.issuer_url)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    client = OAuth2Client(
        row.client_id,
        crypto.decrypt(row.client_secret_encrypted),
        scope=row.scopes,
        redirect_uri=callback_uri(request),
        code_challenge_method="S256",
        **_client_kwargs(),
    )
    with client:
        url, _ = client.create_authorization_url(
            doc["authorization_endpoint"], state=state, nonce=nonce, code_verifier=verifier
        )
    assert create_s256_code_challenge(verifier) in url
    request.session[SESSION_KEY] = {
        "state": state,
        "nonce": nonce,
        "verifier": verifier,
        "mode": mode,
        "user_id": request.user.pk if request.user.is_authenticated else None,
        "started": int(time.time()),
    }
    return url


def _auth_method(doc):
    supported = doc.get("token_endpoint_auth_methods_supported")
    if supported and "client_secret_basic" not in supported and "client_secret_post" in supported:
        return "client_secret_post"
    return "client_secret_basic"


def complete_flow(request):
    """Check the callback. Return (flow, claims). Raise OIDCError with a safe message."""
    flow = request.session.pop(SESSION_KEY, None)
    if not flow or time.time() - flow.get("started", 0) > FLOW_MAX_AGE:
        raise OIDCError("The sign-in request expired. Start again.")
    if request.GET.get("error"):
        raise OIDCError("The provider refused the sign-in.")
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")
    if not code or not hmac.compare_digest(state.encode(), flow["state"].encode()):
        raise OIDCError("The sign-in request could not be checked. Start again.")
    row = get_settings()
    if not (row.enabled and is_configured(row)):
        raise OIDCError("OIDC sign-in is not available.")
    doc = discover(row.issuer_url)
    client = OAuth2Client(
        row.client_id,
        crypto.decrypt(row.client_secret_encrypted),
        token_endpoint_auth_method=_auth_method(doc),
        redirect_uri=callback_uri(request),
        code_challenge_method="S256",
        **_client_kwargs(),
    )
    try:
        with client:
            token = client.fetch_token(doc["token_endpoint"], code=code, code_verifier=flow["verifier"])
    except Exception as exc:  # Authlib and httpx raise several types
        log.warning("OIDC token exchange failed: %s", type(exc).__name__)
        raise OIDCError("The provider did not accept the sign-in.")
    id_token = token.get("id_token")
    if not id_token:
        raise OIDCError("The provider sent no ID token.")
    claims = verify_id_token(id_token, doc, row, flow["nonce"])
    return flow, claims


def verify_id_token(id_token, doc, row, nonce):
    jwks = _get_json(doc["jwks_uri"])
    try:
        decoded = jwt.decode(id_token, KeySet.import_key_set(jwks), algorithms=ID_TOKEN_ALGS)
        registry = jwt.JWTClaimsRegistry(
            leeway=60,
            iss={"essential": True, "value": doc["issuer"]},
            aud={"essential": True, "value": row.client_id},
            exp={"essential": True},
            sub={"essential": True},
            nonce={"essential": True, "value": nonce},
        )
        registry.validate(decoded.claims)
    except (JoseError, ValueError, KeyError) as exc:
        log.warning("OIDC ID token refused: %s", type(exc).__name__)
        raise OIDCError("The ID token from the provider was not valid.")
    claims = decoded.claims
    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != row.client_id:
        raise OIDCError("The ID token from the provider was not valid.")
    return claims


# Identities -------------------------------------------------------------------------


def find_user(claims):
    """Return the active user linked to this issuer and subject, or None. Never matches by e-mail."""
    ident = OIDCIdentity.objects.select_related("user").filter(issuer=claims["iss"], subject=claims["sub"]).first()
    if ident and ident.user.is_active:
        return ident.user
    return None


@transaction.atomic
def link_identity(user, claims, via, actor=None):
    if OIDCIdentity.objects.filter(issuer=claims["iss"], subject=claims["sub"]).exists():
        raise OIDCError("That OIDC account is already linked to a user.")
    if OIDCIdentity.objects.filter(user=user, issuer=claims["iss"]).exists():
        raise OIDCError("Your account already has an OIDC link for this provider.")
    ident = OIDCIdentity.objects.create(user=user, issuer=claims["iss"], subject=claims["sub"])
    record_audit("oidc_linked", actor or user, user, via=via)
    return ident


@transaction.atomic
def unlink_identity(user):
    if not user.has_usable_password():
        raise OIDCError("Set a password first. Without one you could not sign in after unlinking.")
    idents = OIDCIdentity.objects.filter(user=user)
    if not idents.exists():
        raise OIDCError("No OIDC account is linked.")
    idents.delete()
    record_audit("oidc_unlinked", user, user)


def username_for(claims):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    base = (claims.get("preferred_username") or str(claims.get("email", "")).split("@")[0] or "user").strip()
    base = "".join(c for c in base if c.isalnum() or c in "@.+-_")[:120] or "user"
    name, n = base, 1
    while User.objects.filter(username__iexact=name).exists():
        n += 1
        name = f"{base}{n}"
    return name


def signup_from_invitation(raw_token, claims):
    """Create the invited user, link the identity and use up the invitation. All or nothing."""
    from accounts.services import AccountError, create_user
    from invitations import services as inv  # written by the invitations app

    if OIDCIdentity.objects.filter(issuer=claims["iss"], subject=claims["sub"]).exists():
        raise OIDCError("That OIDC account is already linked to a user.")
    try:
        invitation = inv.get_valid(raw_token)
    except inv.InvitationError as exc:
        raise OIDCError(exc.message)
    try:
        with transaction.atomic():
            user = create_user(None, username_for(claims), password=None, role=invitation.role, via="oidc_invitation")
            inv.accept_with_user(raw_token, user)
            OIDCIdentity.objects.create(user=user, issuer=claims["iss"], subject=claims["sub"])
            record_audit("oidc_linked", user, user, via="invitation")
    except (AccountError, inv.InvitationError) as exc:
        raise OIDCError(getattr(exc, "message", None) or str(exc))
    return user
