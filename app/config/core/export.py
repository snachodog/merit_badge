"""Export of one account's core personal data (PLAN.md 13.3).

The format is described in docs/schemas/personal-export.md. Only the given
user's rows are read. Evidence files go in a separate zip archive.
"""
import json
import re
import tempfile
import zipfile

from django.conf import settings
from django.utils import timezone

from achievements.models import AchievementRecord
from achievements.services import display_name_for
from evidence import storage
from evidence.models import EvidenceRecord
from learning.models import LearningPlan, RequirementProgress

FORMAT = "merit-badge-personal-export"
FORMAT_VERSION = "1.0"


def _iso(value):
    return value.isoformat() if value else None


def _source(source):
    if not source:
        return None
    return {
        "title": source.title,
        "publisher_or_creator": source.publisher_or_creator,
        "url": source.url,
        "source_type": source.source_type,
        "review_status": source.review_status,
    }


def archive_path(record):
    """Path of a record's file inside the evidence zip. Built from ids and a clean name."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", record.original_filename or "file").strip("._") or "file"
    return f"evidence/plan-{record.progress.learning_plan_id}/{record.pk}-{name}"


def _evidence(record):
    has_file = bool(record.storage_key)
    return {
        "id": record.pk,
        "evidence_type": record.evidence_type,
        "title": record.title,
        "description": record.description,
        "external_url": record.external_url,
        "file": {
            "original_filename": record.original_filename,
            "content_type": record.content_type,
            "size_bytes": record.size_bytes,
            "sha256": record.sha256,
            "archive_path": archive_path(record),
        } if has_file else None,
        "review_status": record.review_status,
        "reviewer_name_or_label": record.reviewer_name_or_label,
        "review_notes": record.review_notes,
        "retention_status": record.retention_status,
        "created_at": _iso(record.created_at),
    }


def _achievement(record):
    return {
        "id": record.pk,
        "learning_plan_id": record.learning_plan_id,
        "achievement_type": record.achievement_type,
        "display_title": record.display_title,
        "program_name": record.program_name,
        "requirement_version_label": record.requirement_version_label,
        "completed_at": _iso(record.completed_at),
        "completion_basis": record.completion_basis,
        "disclaimer_text_version": record.disclaimer_text_version,
        "learner_display_name": record.learner_display_name,
        "issuer_name": record.issuer_name,
        "official": False,
    }


def build_export(user):
    """A JSON-ready dict with this user's plans, progress, evidence metadata and records."""
    plans = (
        LearningPlan.objects.filter(user=user)
        .select_related("award_version__award__program__owner")
        .order_by("pk")
    )
    out_plans = []
    for plan in plans:
        version = plan.award_version
        rows = (
            RequirementProgress.objects.filter(learning_plan=plan)
            .select_related("requirement_node__source")
            .prefetch_related("evidence_records")
            .order_by("requirement_node__pk")
        )
        requirements = []
        for p in rows:
            n = p.requirement_node
            requirements.append({
                "requirement_id": n.pk,
                "display_number": n.display_number,
                "text": n.text,
                "text_origin": n.text_origin,
                "source": _source(n.source),
                "status": p.status,
                "prior_knowledge_claim": p.prior_knowledge_claim,
                "prior_work_notes": p.prior_work_notes,
                "learner_notes": p.learner_notes,
                "self_attested_at": _iso(p.self_attested_at),
                "personally_completed_at": _iso(p.personally_completed_at),
                "evidence": [_evidence(e) for e in p.evidence_records.all()],
            })
        achievement = AchievementRecord.objects.filter(learning_plan=plan).first()
        out_plans.append({
            "id": plan.pk,
            "title": plan.title,
            "status": plan.status,
            "started_at": _iso(plan.started_at),
            "target_date": _iso(plan.target_date),
            "personal_completed_at": _iso(plan.personal_completed_at),
            "notes": plan.notes,
            "condition_answers": plan.condition_answers,
            "version": {
                "award_version_id": version.pk,
                "version_label": version.version_label,
                "award_name": version.award.name,
                "program_name": version.award.program.name,
                "program_owner": version.award.program.owner.name,
                "is_custom_program": version.award.program.is_custom,
                "published_at": _iso(version.published_at),
                "effective_from": _iso(version.effective_from),
                "effective_until": _iso(version.effective_until),
                "source_status": version.source_status,
                "rights_status": version.rights_status,
            },
            "status_log": [
                {
                    "from_status": log.from_status,
                    "to_status": log.to_status,
                    "changed_at": _iso(log.changed_at),
                    "note": log.note,
                }
                for log in plan.status_log.all()
            ],
            "requirements": requirements,
            "achievement_id": achievement.pk if achievement else None,
        })
    records = AchievementRecord.objects.filter(learning_plan__user=user).order_by("pk")
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "exported_at": _iso(timezone.now()),
        "app_name": settings.APP_NAME,
        "notice": "Personal, unofficial learning records. Not official awards.",
        "account": {"username": user.get_username(), "display_name": display_name_for(user)},
        "learning_plans": out_plans,
        "achievements": [_achievement(r) for r in records],
    }


def build_evidence_zip(user):
    """Write this user's evidence files to a temporary zip. Returns an open file at offset 0."""
    records = (
        EvidenceRecord.objects.filter(progress__learning_plan__user=user)
        .exclude(storage_key="")
        .select_related("progress")
        .order_by("pk")
    )
    tmp = tempfile.TemporaryFile()
    included, missing = [], []
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in records:
            path = archive_path(rec)
            try:
                with storage.get_storage().open(rec.storage_key, "rb") as handle:
                    with zf.open(path, "w", force_zip64=True) as out:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            out.write(chunk)
            except (FileNotFoundError, OSError):
                missing.append(rec.pk)
                continue
            included.append({"evidence_id": rec.pk, "path": path, "sha256": rec.sha256})

        manifest = {
            "format": FORMAT + "-evidence",
            "format_version": FORMAT_VERSION,
            "exported_at": _iso(timezone.now()),
            "files": included,
            "missing_evidence_ids": missing,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    tmp.seek(0)
    return tmp
