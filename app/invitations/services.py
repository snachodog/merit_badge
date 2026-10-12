"""Invitation rules. Views call these.

Hooks for the OIDC app:
- `get_valid(raw_token)` checks a token. It raises `InvitationError` if the link is not usable.
- `accept_with_user(raw_token, user)` marks an invitation used for a user you already created.
  Call it inside your own transaction. It also raises `InvitationError`.
- The accept page stores the raw token in `request.session[SESSION_KEY]` ("invite_token").
"""
import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import Role
from accounts.services import AccountError, create_user, record_audit

from .models import Invitation

SESSION_KEY = "invite_token"
DEFAULT_DAYS = 7
MAX_DAYS = 30

# One message for unknown, used, revoked and expired links, so a visitor learns nothing.
GENERIC_MESSAGE = "This invitation link does not work. It may be used, expired or withdrawn. Ask for a new link."


class InvitationError(Exception):
    """`reason` is one of: invalid, expired, used, revoked. `message` is safe for visitors."""

    def __init__(self, reason):
        self.reason = reason
        self.message = GENERIC_MESSAGE
        super().__init__(reason)


def hash_token(raw_token):
    return hashlib.sha256((raw_token or "").encode()).hexdigest()


@transaction.atomic
def create_invitation(actor, role=Role.USER, days=DEFAULT_DAYS, label=""):
    """Return `(invitation, raw_token)`. The raw token is not stored and cannot be shown again."""
    if role not in Role.values:
        raise AccountError("Choose a role from the list.")
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise AccountError("Enter the number of days as a whole number.")
    if not 1 <= days <= MAX_DAYS:
        raise AccountError(f"Choose between 1 and {MAX_DAYS} days.")
    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        token_hash=hash_token(raw_token),
        role=role,
        label=(label or "").strip()[:100],
        created_by=actor,
        expires_at=timezone.now() + timedelta(days=days),
    )
    record_audit("invitation_created", actor, None, invitation=invitation.pk, role=role, days=days)
    return invitation, raw_token


@transaction.atomic
def revoke(actor, invitation):
    invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
    if invitation.status != "active":
        raise AccountError(f"This invitation is {invitation.status}. Only active invitations can be revoked.")
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at"])
    record_audit("invitation_revoked", actor, None, invitation=invitation.pk)
    return invitation


def _check(invitation):
    if invitation is None:
        raise InvitationError("invalid")
    if invitation.used_at:
        raise InvitationError("used")
    if invitation.revoked_at:
        raise InvitationError("revoked")
    if invitation.expires_at <= timezone.now():
        raise InvitationError("expired")


def get_valid(raw_token):
    """Return the usable invitation for this token, or raise InvitationError.

    The lookup is by SHA-256 hash of a 256-bit random value, so no secret is compared directly.
    """
    invitation = Invitation.objects.filter(token_hash=hash_token(raw_token)).first()
    _check(invitation)
    return invitation


def _lock_valid(raw_token):
    invitation = Invitation.objects.select_for_update().filter(token_hash=hash_token(raw_token)).first()
    _check(invitation)
    return invitation


def _mark_used(invitation, user):
    invitation.used_at = timezone.now()
    invitation.used_by = user
    invitation.save(update_fields=["used_at", "used_by"])
    record_audit("invitation_used", user, user, invitation=invitation.pk, role=invitation.role)


@transaction.atomic
def accept(raw_token, username, password):
    """Create the invited user with a password and use up the invitation."""
    invitation = _lock_valid(raw_token)
    user = create_user(
        invitation.created_by, username, password, role=invitation.role, invitation=invitation.pk
    )
    _mark_used(invitation, user)
    return user


@transaction.atomic
def accept_with_user(raw_token, user):
    """Use up an invitation for a user that already exists (for example from OIDC sign-up).

    The caller creates the user and sets the role from `get_valid(raw_token).role`.
    """
    invitation = _lock_valid(raw_token)
    _mark_used(invitation, user)
    return invitation
