"""Account rules. Views call these; they hold the permission and safety logic.

Extension points for invitations and OIDC: `create_user`, `record_audit`, `AccountError`.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import AuditRecord, Profile, Role


class AccountError(Exception):
    """A refused account change. The message is safe to show to the admin."""


def record_audit(event, actor=None, target=None, **detail):
    return AuditRecord.objects.create(
        event=event,
        actor=actor,
        target=target,
        actor_label=actor.get_username() if actor else "",
        target_label=target.get_username() if target else "",
        detail=detail,
    )


def ensure_profile(user):
    """Return the user's profile. Make one if missing.

    Staff and superusers are admins. So is the first user, when no admin exists yet.
    """
    try:
        return user.profile
    except Profile.DoesNotExist:
        pass
    is_admin = user.is_superuser or user.is_staff or not Profile.objects.filter(role=Role.ADMIN).exists()
    profile = Profile.objects.create(user=user, role=Role.ADMIN if is_admin else Role.USER)
    user.profile = profile
    return profile


def is_admin(user):
    if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    return ensure_profile(user).role == Role.ADMIN


def active_admins():
    return Profile.objects.filter(role=Role.ADMIN, user__is_active=True)


def _would_remove_last_admin(user):
    """True if `user` is an active admin and nobody else is."""
    return is_admin(user) and not active_admins().exclude(user=user).exists()


LAST_ADMIN = "This is the last active admin. Make another user an admin first."


@transaction.atomic
def set_role(actor, user, role):
    if role not in Role.values:
        raise AccountError("Choose a role from the list.")
    profile = ensure_profile(user)
    if profile.role == role:
        return profile
    if role != Role.ADMIN and _would_remove_last_admin(user):
        raise AccountError(LAST_ADMIN)
    old = profile.role
    profile.role = role
    profile.save(update_fields=["role", "updated_at"])
    record_audit("role_changed", actor, user, old=old, new=role)
    return profile


@transaction.atomic
def deactivate(actor, user):
    if _would_remove_last_admin(user):
        raise AccountError(LAST_ADMIN)
    if user.is_active:
        user.is_active = False
        user.save(update_fields=["is_active"])
        record_audit("user_deactivated", actor, user)
    return user


@transaction.atomic
def reactivate(actor, user):
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        record_audit("user_reactivated", actor, user)
    return user


@transaction.atomic
def delete_user(actor, user):
    """Delete the account and, by cascade, its plans and evidence rows."""
    if _would_remove_last_admin(user):
        raise AccountError(LAST_ADMIN)
    label = user.get_username()
    record_audit("user_deleted", actor, None, username=label)
    user.delete()


def _check_password(user, password):
    try:
        validate_password(password, user)
    except ValidationError as exc:
        raise AccountError(" ".join(exc.messages))


@transaction.atomic
def reset_password(actor, user, new_password):
    _check_password(user, new_password)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    record_audit("password_reset", actor, user)
    return user


@transaction.atomic
def create_user(actor, username, password=None, role=Role.USER, email="", **audit_detail):
    """Create an account. `password=None` makes an unusable password (for OIDC-only users)."""
    User = get_user_model()
    if role not in Role.values:
        raise AccountError("Choose a role from the list.")
    if not username or User.objects.filter(username__iexact=username).exists():
        raise AccountError("That username is empty or already taken.")
    user = User(username=username, email=email)
    if password:
        _check_password(user, password)
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.save()
    profile = ensure_profile(user)
    if profile.role != role:
        profile.role = role
        profile.save(update_fields=["role", "updated_at"])
    record_audit("user_created", actor, user, role=role, **audit_detail)
    return user
