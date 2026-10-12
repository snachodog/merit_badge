from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.decorators import admin_required

from . import services
from .forms import OIDCSettingsForm
from .models import OIDCIdentity
from .services import OIDCError

FAILED = "Sign-in with OIDC did not work. Use your password, or ask an admin."


def _start(request, mode, fail_url):
    try:
        return HttpResponseRedirect(services.begin_flow(request, mode))
    except OIDCError as exc:
        messages.error(request, str(exc))
        return redirect(fail_url)


@require_GET
@never_cache
def oidc_login(request):
    """Start sign-in. `?intent=invite` starts sign-up for the invitation held in the session."""
    if request.GET.get("intent") == "invite":
        if not request.session.get(services.INVITE_KEY):
            messages.error(request, "Open your invitation link first.")
            return redirect("login")
        return _start(request, "invite", "login")
    return _start(request, "login", "login")


@login_required
@require_POST
def oidc_link(request):
    return _start(request, "link", "settings")


@login_required
@require_POST
def oidc_unlink(request):
    try:
        services.unlink_identity(request.user)
        messages.success(request, "OIDC account unlinked. Sign in with your password.")
    except OIDCError as exc:
        messages.error(request, str(exc))
    return redirect("settings")


@require_GET
@never_cache
def oidc_callback(request):
    try:
        flow, claims = services.complete_flow(request)
    except OIDCError as exc:
        messages.error(request, str(exc))
        return redirect("settings" if request.user.is_authenticated else "login")
    mode = flow["mode"]
    try:
        if mode == "link":
            if not request.user.is_authenticated or request.user.pk != flow.get("user_id"):
                raise OIDCError("Sign in first, then link your OIDC account.")
            services.link_identity(request.user, claims, via="settings")
            messages.success(request, "OIDC account linked.")
            return redirect("settings")
        if mode == "invite":
            token = request.session.get(services.INVITE_KEY)
            if not token:
                raise OIDCError("Open your invitation link first.")
            user = services.signup_from_invitation(token, claims)
            request.session.pop(services.INVITE_KEY, None)
        else:
            user = services.find_user(claims)
            if user is None:
                raise OIDCError(FAILED)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("home")
    except OIDCError as exc:
        messages.error(request, str(exc))
        return redirect("settings" if mode == "link" else "login")


# Admin settings -------------------------------------------------------------------------


def settings_form(data=None):
    row = services.get_settings()
    initial = {
        "enabled": row.enabled,
        "issuer_url": row.issuer_url,
        "client_id": row.client_id,
        "scopes": row.scopes,
        "button_label": row.button_label,
    }
    return OIDCSettingsForm(data, initial=initial, secret_set=services.secret_is_usable(row) and bool(row.client_secret_encrypted))


@admin_required
@never_cache
@require_http_methods(["GET", "POST"])
def oidc_settings(request):
    form = settings_form(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.save_settings(request.user, form.cleaned_data)
        messages.success(request, "OIDC settings saved. Password sign-in stays available.")
        return redirect("settings")
    return render(request, "oidc/settings.html", {"oidc_form": form, "oidc_redirect_uri": services.callback_uri(request)})


@admin_required
@require_POST
def oidc_test(request):
    ok, message = services.test_discovery(services.get_settings())
    (messages.success if ok else messages.error)(request, message)
    return redirect("settings")
