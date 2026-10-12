"""Who may see and edit programs, and who may change sharing."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404
from django.core.exceptions import PermissionDenied

from accounts import services as accounts
from accounts.services import AccountError

from .models import Program, ProgramShare


def visible_programs(user):
    return Program.objects.visible_to(user)


def can_view(user, program):
    return visible_programs(user).filter(pk=program.pk).exists()


def can_edit(user, program):
    """Creators edit their own programs. Admins also edit system programs (no creator).
    Nobody edits another user's private program."""
    if program.created_by_id is not None:
        return program.created_by_id == user.pk
    return accounts.is_admin(user)


def require_view(user, program):
    """404 if the user cannot see the program."""
    if not can_view(user, program):
        raise Http404("No such program.")


def require_edit(user, program):
    """404 if hidden, 403 if visible but read-only for this user."""
    require_view(user, program)
    if not can_edit(user, program):
        raise PermissionDenied("You cannot edit this program.")


def can_share(user, program):
    return accounts.is_admin(user) and can_edit(user, program)


@transaction.atomic
def set_visibility(actor, program, visibility, users=()):
    if not can_share(actor, program):
        raise PermissionDenied("Only an admin can change sharing.")
    if visibility not in Program.Visibility.values:
        raise AccountError("Choose who can see this program.")
    chosen = {u.pk: u for u in users if u.pk != program.created_by_id and u.is_active}
    if visibility != Program.Visibility.SHARED:
        chosen = {}
    old = program.visibility
    old_ids = set(program.shares.values_list("user_id", flat=True))
    program.visibility = visibility
    program.save(update_fields=["visibility", "updated_at"])
    program.shares.exclude(user_id__in=chosen).delete()
    for uid in chosen:
        ProgramShare.objects.get_or_create(program=program, user_id=uid)
    if old != visibility or old_ids != set(chosen):
        accounts.record_audit(
            "program_visibility_changed", actor, program.created_by,
            program=program.name, program_id=program.pk, old=old, new=visibility,
            shared_with=sorted(u.get_username() for u in chosen.values()),
        )
