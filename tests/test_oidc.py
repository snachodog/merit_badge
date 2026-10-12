"""OIDC sign-in with a fake provider. No network: httpx is wired to a mock transport."""
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from joserfc import jwt
from joserfc.jwk import RSAKey

from accounts.models import AuditRecord, Role
from accounts.services import create_user
from oidc import crypto, services
from oidc.models import OIDCIdentity, OIDCSettings

pytestmark = pytest.mark.django_db
User = get_user_model()
ISSUER = "https://idp.test/app"
CLIENT_ID = "merit-client"
SECRET = "s3cret-value-xyz"


class FakeProvider:
    def __init__(self):
        self.key = RSAKey.generate_key(2048, parameters={"kid": "k1", "use": "sig"})
        self.claims = {}
        self.expect_nonce = None
        self.last_form = None
        self.last_auth = None

    def id_token(self, sub="sub-1", **over):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": CLIENT_ID, "sub": sub, "exp": now + 300, "iat": now,
                  "nonce": self.expect_nonce, "preferred_username": "Alex"}
        claims.update(over)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode({"alg": "RS256", "kid": "k1"}, claims, self.key)

    def handler(self, request):
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={
                "issuer": self.claims.get("doc_issuer", ISSUER),
                "authorization_endpoint": "https://idp.test/authorize",
                "token_endpoint": "https://idp.test/token",
                "jwks_uri": "https://idp.test/jwks",
            })
        if path == "/jwks":
            return httpx.Response(200, json={"keys": [self.key.as_dict(private=False)]})
        if path == "/token":
            self.last_form = parse_qs(request.content.decode())
            self.last_auth = request.headers.get("authorization")
            return httpx.Response(200, json={
                "access_token": "at", "token_type": "Bearer", "id_token": self.claims["token"](),
            })
        return httpx.Response(404)


@pytest.fixture
def idp(monkeypatch):
    cache.clear()
    p = FakeProvider()
    monkeypatch.setattr(services, "HTTP_TRANSPORT", httpx.MockTransport(p.handler))
    p.claims["token"] = lambda: p.id_token()
    return p


@pytest.fixture
def configured(db):
    admin = User.objects.create_user("boss", password="pw-long-enough-1")
    services.save_settings(admin, {
        "enabled": True, "issuer_url": ISSUER, "client_id": CLIENT_ID, "client_secret": SECRET,
        "scopes": "openid email profile", "button_label": "Sign in with Authentik",
    })
    return admin


@pytest.fixture
def member(configured):
    return create_user(None, "kim", password="pw-long-enough-2")


def run_login(client, idp, path="/oidc/login/", state_override=None, **token_over):
    resp = client.get(path)
    assert resp.status_code == 302, resp.content
    q = parse_qs(urlparse(resp["Location"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["response_type"] == ["code"]
    idp.expect_nonce = q["nonce"][0]
    idp.claims["token"] = lambda: idp.id_token(**token_over)
    return client.get(reverse("oidc_callback"), {"code": "abc", "state": state_override or q["state"][0]})


def link(user, sub="sub-1"):
    return OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject=sub)


def signed_in(client, user):
    client.force_login(user)


# Settings ----------------------------------------------------------------------------


def test_settings_post_admin_only(client, configured, member):
    url = reverse("oidc_settings")
    assert client.post(url, {}).status_code == 302  # anonymous: to login
    client.force_login(member)
    assert client.post(url, {"scopes": "openid", "button_label": "x"}).status_code == 403
    assert client.post(reverse("oidc_test")).status_code == 403
    assert 'id="oidc-h"' not in client.get(reverse("settings")).content.decode()


def test_secret_encrypted_and_never_rendered(client, configured):
    row = OIDCSettings.objects.get()
    assert SECRET not in row.client_secret_encrypted
    assert crypto.decrypt(row.client_secret_encrypted) == SECRET
    client.force_login(configured)
    for url in (reverse("settings"), reverse("oidc_settings")):
        body = client.get(url).content.decode()
        assert SECRET not in body and row.client_secret_encrypted not in body
        assert "A secret is set" in body
    assert "/oidc/callback/" in client.get(reverse("settings")).content.decode()


def test_blank_secret_keeps_current(client, configured):
    client.force_login(configured)
    resp = client.post(reverse("oidc_settings"), {
        "enabled": "on", "issuer_url": ISSUER, "client_id": "other", "client_secret": "",
        "scopes": "openid profile", "button_label": "Go"})
    assert resp.status_code == 302
    row = OIDCSettings.objects.get()
    assert row.client_id == "other" and crypto.decrypt(row.client_secret_encrypted) == SECRET
    event = AuditRecord.objects.filter(event="oidc_settings_changed").first()
    assert SECRET not in str(event.detail)


def test_cannot_enable_without_required_fields(client, db):
    admin = User.objects.create_user("boss", password="pw-long-enough-1")
    client.force_login(admin)
    resp = client.post(reverse("oidc_settings"), {
        "enabled": "on", "issuer_url": "", "client_id": "", "scopes": "openid", "button_label": "Go"})
    assert resp.status_code == 200
    assert "enter the issuer URL, client ID, client secret" in resp.content.decode()
    assert not services.get_settings().enabled


def test_issuer_needs_https_except_localhost(client, db):
    assert services.issuer_problem("http://idp.example.com")
    assert not services.issuer_problem("http://localhost:9000/x")
    assert not services.issuer_problem("https://idp.example.com")


def test_env_prefill(monkeypatch, db):
    monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", SECRET)
    monkeypatch.setenv("OIDC_ENABLED", "true")
    row = services.get_settings()
    assert row.enabled and row.issuer_url == ISSUER and SECRET not in row.client_secret_encrypted


def test_discovery_test_button(client, configured, idp):
    client.force_login(configured)
    resp = client.post(reverse("oidc_test"), follow=True)
    assert "Discovery works" in resp.content.decode() and SECRET not in resp.content.decode()
    idp.claims["doc_issuer"] = "https://evil.test"
    resp = client.post(reverse("oidc_test"), follow=True)
    assert "does not match" in resp.content.decode()


def test_secret_unreadable_after_key_change(configured, settings):
    settings.SECRET_KEY = "a-different-secret-key"
    assert not services.secret_is_usable(services.get_settings())
    assert not services.is_available()


# Sign-in -----------------------------------------------------------------------------


def test_login_button_only_when_enabled(client, configured):
    assert "Sign in with Authentik" in client.get(reverse("login")).content.decode()
    OIDCSettings.objects.update(enabled=False)
    body = client.get(reverse("login")).content.decode()
    assert "Sign in with Authentik" not in body and 'name="password"' in body


def test_login_for_linked_identity(client, idp, member):
    link(member)
    resp = run_login(client, idp)
    assert resp.status_code == 302 and resp["Location"] == reverse("home")
    assert client.session["_auth_user_id"] == str(member.pk)
    assert idp.last_form["code_verifier"] and idp.last_auth.startswith("Basic ")


def test_unknown_subject_refused_no_account(client, idp, member):
    link(member, sub="someone-else")
    before = User.objects.count()
    resp = run_login(client, idp, sub="stranger")
    assert resp["Location"] == reverse("login")
    assert "_auth_user_id" not in client.session and User.objects.count() == before


def test_email_never_matches(client, idp, member):
    member.email = "kim@example.com"
    member.save()
    resp = run_login(client, idp, sub="new", email="kim@example.com")
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize("over", [
    {"aud": "someone-else"},
    {"iss": "https://evil.test"},
    {"exp": int(time.time()) - 3600},
    {"nonce": "wrong"},
])
def test_bad_token_refused(client, idp, member, over):
    link(member)
    run_login(client, idp, **over)
    assert "_auth_user_id" not in client.session


def test_bad_signature_refused(client, idp, member):
    link(member)
    other = RSAKey.generate_key(2048, parameters={"kid": "k1"})
    resp = client.get("/oidc/login/")
    q = parse_qs(urlparse(resp["Location"]).query)
    now = int(time.time())
    idp.claims["token"] = lambda: jwt.encode(
        {"alg": "RS256", "kid": "k1"},
        {"iss": ISSUER, "aud": CLIENT_ID, "sub": "sub-1", "exp": now + 99, "nonce": q["nonce"][0]}, other)
    client.get(reverse("oidc_callback"), {"code": "abc", "state": q["state"][0]})
    assert "_auth_user_id" not in client.session


def test_wrong_state_refused(client, idp, member):
    link(member)
    run_login(client, idp, state_override="forged")
    assert "_auth_user_id" not in client.session


def test_callback_without_flow_refused(client, idp, member):
    link(member)
    client.get(reverse("oidc_callback"), {"code": "abc", "state": "x"})
    assert "_auth_user_id" not in client.session


def test_inactive_user_refused(client, idp, member):
    link(member)
    member.is_active = False
    member.save()
    run_login(client, idp)
    assert "_auth_user_id" not in client.session


def test_provider_error_refused(client, idp, member):
    client.get("/oidc/login/")
    resp = client.get(reverse("oidc_callback"), {"error": "access_denied"})
    assert resp["Location"] == reverse("login")


def test_login_unavailable_when_disabled(client, idp, member):
    OIDCSettings.objects.update(enabled=False)
    resp = client.get("/oidc/login/")
    assert resp["Location"] == reverse("login")


def test_password_login_works_either_way(client, member):
    assert client.login(username="kim", password="pw-long-enough-2")
    client.logout()
    OIDCSettings.objects.update(enabled=False)
    assert client.login(username="kim", password="pw-long-enough-2")


# Link and unlink -------------------------------------------------------------------------


def test_link_flow(client, idp, member):
    client.force_login(member)
    assert client.get(reverse("oidc_link")).status_code == 405
    resp = client.post(reverse("oidc_link"))
    q = parse_qs(urlparse(resp["Location"]).query)
    idp.expect_nonce = q["nonce"][0]
    idp.claims["token"] = lambda: idp.id_token(sub="kim-sub")
    resp = client.get(reverse("oidc_callback"), {"code": "abc", "state": q["state"][0]})
    assert resp["Location"] == reverse("settings")
    assert OIDCIdentity.objects.get(user=member).subject == "kim-sub"
    assert AuditRecord.objects.filter(event="oidc_linked", target=member).exists()
    assert "Unlink OIDC account" in client.get(reverse("settings")).content.decode()


def test_link_refuses_identity_of_another_user(client, idp, member, configured):
    link(configured, sub="sub-1")
    client.force_login(member)
    resp = client.post(reverse("oidc_link"))
    q = parse_qs(urlparse(resp["Location"]).query)
    idp.expect_nonce = q["nonce"][0]
    idp.claims["token"] = lambda: idp.id_token(sub="sub-1")
    client.get(reverse("oidc_callback"), {"code": "abc", "state": q["state"][0]})
    assert not OIDCIdentity.objects.filter(user=member).exists()


def test_link_needs_login(client, idp, configured):
    assert client.post(reverse("oidc_link")).status_code == 302
    assert "login" in client.post(reverse("oidc_link"))["Location"]


def test_unlink_rules(client, member):
    link(member)
    client.force_login(member)
    client.post(reverse("oidc_unlink"))
    assert not OIDCIdentity.objects.filter(user=member).exists()
    assert AuditRecord.objects.filter(event="oidc_unlinked").exists()
    # no usable password: cannot unlink
    nopw = create_user(None, "oidconly", password=None)
    link(nopw, sub="s2")
    client.force_login(nopw)
    client.post(reverse("oidc_unlink"))
    assert OIDCIdentity.objects.filter(user=nopw).exists()


# Invitation sign-up ------------------------------------------------------------------------


def test_invitation_signup(client, idp, configured):
    from invitations import services as inv

    _, raw = inv.create_invitation(configured, role=Role.USER)
    session = client.session
    session["invite_token"] = raw
    session.save()
    resp = run_login(client, idp, path="/oidc/login/?intent=invite", sub="new-sub")
    assert resp["Location"] == reverse("home")
    user = User.objects.get(username="Alex")
    assert not user.has_usable_password()
    assert OIDCIdentity.objects.get(user=user).subject == "new-sub"
    assert client.session["_auth_user_id"] == str(user.pk)
    assert "invite_token" not in client.session


def test_invite_intent_needs_token(client, idp, configured):
    resp = client.get("/oidc/login/?intent=invite")
    assert resp["Location"] == reverse("login")


def test_invitation_signup_bad_token_creates_nothing(client, idp, configured):
    session = client.session
    session["invite_token"] = "not-a-real-token"
    session.save()
    before = User.objects.count()
    run_login(client, idp, path="/oidc/login/?intent=invite", sub="new-sub")
    assert User.objects.count() == before and "_auth_user_id" not in client.session
