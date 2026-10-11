"""Evidence services. Views call these; they check ownership and the rules.

`human_observed` is set only by `record_human_observation`, which needs a
reviewer label. Nothing in the AI code path calls it (there is none yet).
"""
import hashlib
import uuid
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied
from django.db import transaction

from learning.models import LearningPlan, RequirementProgress

from . import storage
from .models import EvidenceRecord
from .validation import UploadError, safe_display_name, validate_upload

ET = EvidenceRecord.EvidenceType
RS = EvidenceRecord.ReviewStatus


class EvidenceError(ValueError):
    """The action is not allowed. The message is safe to show."""


def _check_owner(user, progress):
    if progress.learning_plan.user_id != user.pk:
        raise PermissionDenied("This requirement belongs to another account.")


def _check_plan_open(progress):
    from learning.models import LearningPlan as P

    if progress.learning_plan.status in (P.Status.ABANDONED, P.Status.ARCHIVED, P.Status.PERSONALLY_COMPLETED):
        raise EvidenceError("This plan is closed, so you cannot add evidence to it.")


def _check_record_owner(user, record):
    _check_owner(user, record.progress)


def add_text_evidence(
    user, progress, evidence_type, *, title="", description="", external_url=""
):
    """Add evidence that has no file. File types go through `add_file_evidence`."""
    _check_owner(user, progress)
    _check_plan_open(progress)
    if evidence_type in EvidenceRecord.FILE_TYPES:
        raise EvidenceError("Use the file upload for file, image, audio and video evidence.")
    if evidence_type not in ET.values:
        raise EvidenceError(f"Unknown evidence type: {evidence_type!r}.")
    if evidence_type == ET.EXTERNAL_LINK and not external_url:
        raise EvidenceError("A link record needs a URL.")
    if evidence_type != ET.EXTERNAL_LINK and not (title or description):
        raise EvidenceError("Add a title or a description.")
    if external_url and not external_url.startswith(("http://", "https://")):
        raise EvidenceError("The URL must start with http:// or https://.")
    return EvidenceRecord.objects.create(
        progress=progress,
        created_by=user,
        evidence_type=evidence_type,
        title=title[:200],
        description=description,
        external_url=external_url,
    )


def add_time_log(user, progress, *, date, minutes, note=""):
    """One dated time entry. Several entries can be added to one requirement."""
    _check_owner(user, progress)
    _check_plan_open(progress)
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 1440:
        raise EvidenceError("Minutes must be a whole number from 1 to 1440.")
    return EvidenceRecord.objects.create(
        progress=progress,
        created_by=user,
        evidence_type=ET.TIME_LOG,
        title=f"{date.isoformat()}: {minutes} min",
        description=note,
    )


def add_file_evidence(user, progress, uploaded, *, title="", description=""):
    """Validate and store an uploaded file under a generated name."""
    _check_owner(user, progress)
    _check_plan_open(progress)
    try:
        ext, evidence_type, content_type = validate_upload(uploaded)
    except UploadError as exc:
        raise EvidenceError(str(exc)) from exc
    # The key uses only ids, a random token and a checked extension. User input never enters it.
    key = f"{user.pk}/{progress.learning_plan_id}/{uuid.uuid4().hex}{ext}"
    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    uploaded.seek(0)
    saved_key = storage.get_storage().save(key, uploaded)
    try:
        with transaction.atomic():
            return EvidenceRecord.objects.create(
                progress=progress,
                created_by=user,
                evidence_type=evidence_type,
                title=title[:200],
                description=description,
                storage_key=saved_key,
                original_filename=safe_display_name(uploaded.name),
                content_type=content_type,
                size_bytes=uploaded.size,
                sha256=digest.hexdigest(),
            )
    except Exception:
        storage.delete_file(saved_key)
        raise


def attest_evidence(user, record):
    """The learner says this evidence is truthful. Not a review by anyone else."""
    _check_record_owner(user, record)
    record.review_status = RS.LEARNER_ATTESTED
    record.save(update_fields=["review_status"])
    return record


def record_feedback(user, record, *, reviewer_label="", notes=""):
    """The learner records feedback that someone gave them."""
    _check_record_owner(user, record)
    if record.review_status == RS.HUMAN_OBSERVED:
        raise EvidenceError("This evidence is already recorded as human observed.")
    record.review_status = RS.FEEDBACK_RECEIVED
    record.reviewer_name_or_label = reviewer_label.strip()[:200]
    record.review_notes = notes
    record.save(update_fields=["review_status", "reviewer_name_or_label", "review_notes"])
    return record


def record_human_observation(user, record, *, reviewer_label, notes=""):
    """A person records that a named human observed this. Needs a reviewer label.

    This is the only function that sets `human_observed`. AI output cannot use it.
    """
    _check_record_owner(user, record)
    label = (reviewer_label or "").strip()
    if not label:
        raise EvidenceError("Name or describe the person who observed this.")
    if record.evidence_type == ET.AI_PRACTICE_SUMMARY:
        raise EvidenceError("An AI practice summary cannot be recorded as human observed.")
    record.review_status = RS.HUMAN_OBSERVED
    record.reviewer_name_or_label = label[:200]
    record.review_notes = notes
    record.save(update_fields=["review_status", "reviewer_name_or_label", "review_notes"])
    return record


# Deletion -------------------------------------------------------------------------

@dataclass
class DeletionReport:
    records: int = 0
    files: int = 0
    bytes: int = 0
    items: list = field(default_factory=list)

    def summary(self):
        if not self.records:
            return "No evidence will be deleted."
        return (
            f"{self.records} evidence record(s) will be deleted, including "
            f"{self.files} stored file(s) ({self.bytes} bytes). This cannot be undone."
        )


def deletion_report(queryset):
    """Say what deleting these evidence records removes. Changes nothing."""
    report = DeletionReport()
    for rec in queryset:
        report.records += 1
        if rec.storage_key:
            report.files += 1
            report.bytes += rec.size_bytes or 0
        report.items.append(str(rec))
    return report


def deletion_report_for_plan(plan: LearningPlan):
    return deletion_report(EvidenceRecord.objects.filter(progress__learning_plan=plan))


def deletion_report_for_progress(progress: RequirementProgress):
    return deletion_report(progress.evidence_records.all())


@transaction.atomic
def delete_evidence(user, record):
    """Delete one record and its file. Returns what was removed."""
    _check_record_owner(user, record)
    report = deletion_report([record])
    record.delete()  # the post_delete hook removes the file after commit
    return report
