from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import admin_required
from learning import selectors

from . import services
from .forms import AISettingsForm, MessageForm
from .models import TutoringSession

Status = TutoringSession.Status


def _own(request, pk):
    return get_object_or_404(
        TutoringSession.objects.select_related("progress__requirement_node", "progress__learning_plan"),
        pk=pk, user=request.user,
    )


def settings_form(data=None):
    row = services.get_settings()
    initial = {"enabled": row.enabled, "base_url": row.base_url, "model": row.model}
    return AISettingsForm(data, initial=initial, key_set=bool(row.api_key_encrypted) and services.key_is_usable(row))


@admin_required
@never_cache
@require_http_methods(["GET", "POST"])
def ai_settings(request):
    form = settings_form(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.save_settings(request.user, form.cleaned_data)
        messages.success(request, "AI settings saved. The rest of the app works with the tutor off.")
        return redirect("settings")
    return render(request, "tutoring/settings.html", {"ai_form": form})


@admin_required
@require_POST
def ai_test(request):
    ok, message = services.test_connection(services.get_settings())
    (messages.success if ok else messages.error)(request, message)
    return redirect("settings")


@login_required
@require_POST
def session_start(request, progress_pk):
    progress = selectors.get_progress_for(request.user, progress_pk)
    try:
        session = services.start_session(request.user, progress, request.POST.get("mode", ""))
    except services.TutorError as exc:
        messages.error(request, str(exc))
        return redirect("progress_detail", pk=progress.pk)
    return redirect("tutor_session", pk=session.pk)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def session_detail(request, pk):
    session = _own(request, pk)
    form = MessageForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                services.send_message(session, form.cleaned_data["message"])
            except services.TutorError as exc:
                messages.error(request, str(exc))
            else:
                return redirect("tutor_session", pk=session.pk)
        elif session.status == Status.OPEN:
            messages.error(request, "Write a message of up to 2000 characters.")
    return render(request, "tutoring/session.html", {
        "session": session, "form": form, "progress": session.progress, "ai_on": services.is_available(),
    })


@login_required
@require_POST
def session_end(request, pk):
    services.end_session(_own(request, pk))
    return redirect("tutor_session", pk=pk)


@login_required
@require_POST
def session_keep(request, pk):
    session = _own(request, pk)
    try:
        services.keep_session(session, save_transcript=request.POST.get("save_transcript") == "1")
    except services.TutorError as exc:
        messages.error(request, str(exc))
        return redirect("tutor_session", pk=pk)
    messages.success(request, "Session kept.")
    return redirect("tutor_list")


@login_required
@require_POST
def session_discard(request, pk):
    session = _own(request, pk)
    progress_pk = session.progress_id
    services.discard_session(session)
    messages.success(request, "Session deleted.")
    return redirect("progress_detail", pk=progress_pk)


@login_required
def session_list(request):
    sessions = TutoringSession.objects.filter(user=request.user, status=Status.KEPT).select_related(
        "progress__requirement_node", "progress__learning_plan__award_version__award"
    )
    return render(request, "tutoring/list.html", {"sessions": sessions})
