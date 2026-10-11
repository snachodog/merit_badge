from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from learning import selectors

from . import forms, services, storage, validation
from .models import EvidenceRecord


@login_required
@require_GET
def download(request, pk):
    """Send an evidence file to its owner only. Others get 404."""
    record = get_object_or_404(
        EvidenceRecord, pk=pk, progress__learning_plan__user=request.user
    )
    if not record.storage_key:
        raise Http404("This evidence has no file.")
    try:
        handle = storage.get_storage().open(record.storage_key, "rb")
    except (FileNotFoundError, OSError):
        raise Http404("The file is missing from storage.")
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=record.original_filename or "evidence",
        content_type=record.content_type or "application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# Evidence forms ---------------------------------------------------------------------

KINDS = {
    "text": ("Add a note or text response", forms.TextEvidenceForm),
    "link": ("Add a link", forms.LinkEvidenceForm),
    "file": ("Upload a file", forms.FileEvidenceForm),
    "timelog": ("Add a time log entry", forms.TimeLogForm),
}


@login_required
@require_http_methods(["GET", "POST"])
def evidence_add(request, pk, kind):
    progress = selectors.get_progress_for(request.user, pk)
    if kind not in KINDS:
        raise Http404("Unknown kind of evidence.")
    title, form_class = KINDS[kind]
    form = form_class(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if kind == "text":
                services.add_text_evidence(
                    request.user, progress, data["evidence_type"],
                    title=data["title"], description=data["description"],
                )
            elif kind == "link":
                services.add_text_evidence(
                    request.user, progress, "external_link",
                    title=data["title"], description=data["description"],
                    external_url=data["external_url"],
                )
            elif kind == "file":
                services.add_file_evidence(
                    request.user, progress, data["file"],
                    title=data["title"], description=data["description"],
                )
            else:
                services.add_time_log(
                    request.user, progress,
                    date=data["date"], minutes=data["minutes"], note=data["note"],
                )
        except services.EvidenceError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Evidence saved. Adding evidence does not complete the requirement.")
            return redirect("progress_detail", pk=progress.pk)
    return render(request, "evidence/evidence_form.html", {
        "form": form, "title": title, "progress": progress, "kind": kind,
        "multipart": kind == "file",
        "max_mb": validation.max_upload_bytes() // (1024 * 1024),
    })


def _get_record(user, pk):
    return get_object_or_404(
        EvidenceRecord.objects.select_related("progress__learning_plan", "progress__requirement_node"),
        pk=pk, progress__learning_plan__user=user,
    )


@login_required
@require_http_methods(["GET", "POST"])
def evidence_delete(request, pk):
    record = _get_record(request.user, pk)
    progress = record.progress
    if request.method == "POST":
        report = services.delete_evidence(request.user, record)
        messages.success(request, report.summary().replace("will be", "was"))
        return redirect("progress_detail", pk=progress.pk)
    return render(request, "evidence/evidence_delete.html", {
        "record": record, "progress": progress,
        "report": services.deletion_report([record]),
    })


@login_required
@require_http_methods(["GET", "POST"])
def evidence_observe(request, pk):
    record = _get_record(request.user, pk)
    form = forms.ObservationForm(request.POST or None, initial={
        "reviewer_label": record.reviewer_name_or_label, "notes": record.review_notes,
    })
    if request.method == "POST" and form.is_valid():
        try:
            services.record_human_observation(
                request.user, record,
                reviewer_label=form.cleaned_data["reviewer_label"],
                notes=form.cleaned_data["notes"],
            )
        except services.EvidenceError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Saved as observed by a person.")
            return redirect("progress_detail", pk=record.progress_id)
    return render(request, "evidence/evidence_observe.html", {
        "form": form, "record": record, "progress": record.progress,
    })
