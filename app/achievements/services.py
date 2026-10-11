"""Achievement services.

`record_completion` runs inside `learning.services.complete_plan`, after the
engine says the plan is satisfied. Nothing else creates records.
"""
from django.conf import settings

from evidence.models import EvidenceRecord
from learning.models import RequirementProgress

from . import disclaimer
from .models import AchievementRecord, LearnerProfile

CB = AchievementRecord.CompletionBasis


def display_name_for(user):
    """The chosen display name, or the username if none is set."""
    profile = LearnerProfile.objects.filter(user=user).first()
    return (profile.display_name.strip() if profile else "") or user.get_username()


def display_name_raw(user):
    """The saved display name only, empty if none (for the settings form)."""
    profile = LearnerProfile.objects.filter(user=user).first()
    return profile.display_name if profile else ""


def set_display_name(user, name):
    profile, _ = LearnerProfile.objects.get_or_create(user=user)
    profile.display_name = (name or "").strip()[:100]
    profile.save()
    return profile


def completion_basis(plan):
    """Describe how the completed requirements were supported. Honest, not generous."""
    records = EvidenceRecord.objects.filter(
        progress__learning_plan=plan,
        progress__status=RequirementProgress.Status.PERSONALLY_COMPLETED,
    ).exclude(evidence_type=EvidenceRecord.EvidenceType.AI_PRACTICE_SUMMARY)
    if records.filter(review_status=EvidenceRecord.ReviewStatus.HUMAN_OBSERVED).exists():
        return CB.HUMAN_REVIEWED
    if records.exists():
        return CB.EVIDENCE_DOCUMENTED
    return CB.SELF_ATTESTED


def record_completion(plan):
    """Create the record for a personally completed plan. Safe to call twice."""
    existing = AchievementRecord.objects.filter(learning_plan=plan).first()
    if existing:
        return existing
    award = plan.award_version.award
    kind = (
        AchievementRecord.AchievementType.CUSTOM_CERTIFICATE
        if award.program.is_custom
        else AchievementRecord.AchievementType.PERSONAL_LEARNING_RECORD
    )
    return AchievementRecord.objects.create(
        learning_plan=plan,
        achievement_type=kind,
        display_title=plan.title,
        program_name=award.program.name,
        requirement_version_label=plan.award_version.version_label,
        completed_at=plan.personal_completed_at,
        completion_basis=completion_basis(plan),
        disclaimer_text_version=disclaimer.CURRENT_VERSION,
        learner_display_name=display_name_for(plan.user),
        issuer_name=settings.APP_NAME,
    )


def certificate_context(record):
    """Everything the certificate page shows (PLAN.md 12.5)."""
    version = record.learning_plan.award_version
    return {
        "record": record,
        "version": version,
        "disclaimer": disclaimer.disclaimer_text(record.disclaimer_text_version, record.issuer_name),
    }
