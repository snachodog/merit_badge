"""Admin user management. Shows names, roles and status only; no private learner data."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import services
from .decorators import admin_required
from .forms import PasswordResetForm, RoleForm
from .models import Role


def users_context():
    """Context for the Users section. Also used by the Settings page."""
    users = get_user_model().objects.select_related("profile").order_by("username")
    for u in users:
        services.ensure_profile(u)
    return {"users": users, "roles": Role.choices}


@admin_required
def user_list(request):
    return render(request, "accounts/user_list.html", users_context())


@admin_required
@require_POST
def user_role(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    form = RoleForm(request.POST)
    try:
        if not form.is_valid():
            raise services.AccountError("Choose a role from the list.")
        services.set_role(request.user, target, form.cleaned_data["role"])
        messages.success(request, f"Role saved for {target.get_username()}.")
    except services.AccountError as exc:
        messages.error(request, str(exc))
    return redirect("user_list")


@admin_required
@require_POST
def user_active(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    try:
        if request.POST.get("active") == "1":
            services.reactivate(request.user, target)
            messages.success(request, f"{target.get_username()} can sign in again.")
        else:
            services.deactivate(request.user, target)
            messages.success(request, f"{target.get_username()} is deactivated and cannot sign in.")
    except services.AccountError as exc:
        messages.error(request, str(exc))
    return redirect("user_list")


@admin_required
@require_http_methods(["GET", "POST"])
def user_password(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    form = PasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.reset_password(request.user, target, form.cleaned_data["new_password"])
        except services.AccountError as exc:
            form.add_error("new_password", str(exc))
        else:
            messages.success(request, f"Password changed for {target.get_username()}.")
            return redirect("user_list")
    return render(request, "accounts/user_password.html", {"form": form, "target": target})
