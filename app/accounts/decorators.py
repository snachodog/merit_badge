from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .services import is_admin


def admin_required(view):
    """Anonymous users go to the login page. Signed-in non-admins get 403."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied("Only an admin can do this.")
        return view(request, *args, **kwargs)

    return wrapper
