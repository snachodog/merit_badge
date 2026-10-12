import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from achievements import services

from . import export
from .forms import SettingsForm


@require_GET
@never_cache
def healthz(request):
    """Unauthenticated liveness/readiness check. Reveals no details."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception:
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})


@login_required
def home(request):
    from programs import tutorial
    from programs.models import AwardVersion

    tutorial_version = AwardVersion.objects.filter(
        award__program__owner__slug=tutorial.OWNER_SLUG,
        award__slug=tutorial.AWARD_SLUG,
        status=AwardVersion.Status.PUBLISHED,
    ).first()
    return render(request, "home.html", {"tutorial_version": tutorial_version})


# Settings and export ---------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def settings_page(request):
    form = SettingsForm(
        request.POST or None, initial={"display_name": services.display_name_raw(request.user)}
    )
    if request.method == "POST" and form.is_valid():
        services.set_display_name(request.user, form.cleaned_data["display_name"])
        messages.success(request, "Display name saved. Existing certificates keep the name they were issued with.")
        return redirect("settings")
    return render(request, "settings.html", {"form": form})


@login_required
@require_GET
def export_json(request):
    data = export.build_export(request.user)
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False), content_type="application/json"
    )
    stamp = timezone.now().strftime("%Y%m%d")
    response["Content-Disposition"] = f'attachment; filename="personal-export-{stamp}.json"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
def export_evidence_zip(request):
    handle = export.build_evidence_zip(request.user)
    stamp = timezone.now().strftime("%Y%m%d")
    response = FileResponse(
        handle, as_attachment=True, filename=f"evidence-files-{stamp}.zip",
        content_type="application/zip",
    )
    response["Cache-Control"] = "private, no-store"
    return response
