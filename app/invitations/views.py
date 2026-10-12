from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods

from accounts.decorators import admin_required
from accounts.services import AccountError

from . import services
from .forms import AcceptForm, CreateInvitationForm
from .models import Invitation


@admin_required
@require_POST
@never_cache
def invitation_create(request):
    form = CreateInvitationForm(request.POST)
    if form.is_valid():
        try:
            invitation, raw = services.create_invitation(
                request.user, form.cleaned_data["role"], form.cleaned_data["days"], form.cleaned_data["label"]
            )
        except AccountError as exc:
            messages.error(request, str(exc))
            return redirect("settings")
        link = request.build_absolute_uri(f"/invite/{raw}/")
        return render(request, "invitations/created.html", {"invitation": invitation, "link": link})
    for errs in form.errors.values():
        for e in errs:
            messages.error(request, e)
    return redirect("settings")


@admin_required
@require_POST
def invitation_revoke(request, pk):
    invitation = get_object_or_404(Invitation, pk=pk)
    try:
        services.revoke(request.user, invitation)
        messages.success(request, "Invitation revoked.")
    except AccountError as exc:
        messages.error(request, str(exc))
    return redirect("settings")


@never_cache
@require_http_methods(["GET", "POST"])
def invitation_accept(request, token):
    try:
        invitation = services.get_valid(token)
    except services.InvitationError as exc:
        return render(request, "invitations/invalid.html", {"message": exc.message}, status=410)
    request.session[services.SESSION_KEY] = token
    form = AcceptForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = services.accept(token, form.cleaned_data["username"], form.cleaned_data["password"])
        except services.InvitationError as exc:
            return render(request, "invitations/invalid.html", {"message": exc.message}, status=410)
        except AccountError as exc:
            form.add_error(None, str(exc))
        else:
            request.session.pop(services.SESSION_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Welcome to Merit Badge. Your account is ready.")
            return redirect("home")
    return render(request, "invitations/accept.html", {"form": form})
