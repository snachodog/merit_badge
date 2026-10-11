"""Checks for uploaded evidence files. Pure functions; no database.

Order: size, name and extension, declared content type, then the first bytes
for formats that have a fixed signature. Failing any check refuses the file.
"""
import os
import re

from django.conf import settings

# extension -> (evidence type, allowed declared content types)
ALLOWED_UPLOADS = {
    ".jpg": ("image", {"image/jpeg"}),
    ".jpeg": ("image", {"image/jpeg"}),
    ".png": ("image", {"image/png"}),
    ".gif": ("image", {"image/gif"}),
    ".webp": ("image", {"image/webp"}),
    ".pdf": ("file", {"application/pdf"}),
    ".txt": ("file", {"text/plain"}),
    ".mp3": ("audio", {"audio/mpeg", "audio/mp3"}),
    ".m4a": ("audio", {"audio/mp4", "audio/x-m4a", "audio/m4a"}),
    ".wav": ("audio", {"audio/wav", "audio/x-wav", "audio/wave"}),
    ".ogg": ("audio", {"audio/ogg", "application/ogg"}),
    ".mp4": ("video", {"video/mp4"}),
    ".mov": ("video", {"video/quicktime"}),
    ".webm": ("video", {"video/webm"}),
}

SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF-",),
}


class UploadError(ValueError):
    """The file is refused. The message is safe to show to the learner."""


def max_upload_bytes():
    return int(getattr(settings, "EVIDENCE_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))


def safe_display_name(raw):
    """Plain file name for display only. Never used to build a path."""
    name = os.path.basename((raw or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".")
    return name[:150] or "file"


def validate_upload(uploaded):
    """Return (extension, evidence_type, content_type) or raise UploadError."""
    size = getattr(uploaded, "size", None)
    if not size:
        raise UploadError("The file is empty.")
    limit = max_upload_bytes()
    if size > limit:
        raise UploadError(
            f"The file is too large. The limit is {limit // (1024 * 1024)} MB "
            f"({limit} bytes)."
        )
    name = safe_display_name(getattr(uploaded, "name", ""))
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_UPLOADS:
        raise UploadError(
            "This file type is not allowed. Allowed types: "
            + ", ".join(sorted(ALLOWED_UPLOADS))
            + "."
        )
    evidence_type, allowed = ALLOWED_UPLOADS[ext]
    declared = (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()
    if declared not in allowed:
        raise UploadError(
            f"The file says it is {declared or 'unknown'}, which does not match {ext}."
        )
    uploaded.seek(0)
    head = uploaded.read(8192)
    uploaded.seek(0)
    if ext in SIGNATURES and not any(head.startswith(s) for s in SIGNATURES[ext]):
        raise UploadError(f"The file content does not look like a {ext} file.")
    if ext == ".webp" and not (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        raise UploadError("The file content does not look like a .webp file.")
    if ext == ".txt" and b"\x00" in head:
        raise UploadError("The file content does not look like plain text.")
    return ext, evidence_type, declared
