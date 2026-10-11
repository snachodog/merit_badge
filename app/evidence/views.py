from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from . import storage
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
