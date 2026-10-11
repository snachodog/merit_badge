"""Personal achievement records (PLAN.md 6.13).

A record is made only by `achievements.services.record_completion`, which the
plan completion flow calls. There is no other way to create one.
It documents the app's personal completion decision. It is never an official award.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from learning.models import LearningPlan
from programs.models import TimestampedModel


class LearnerProfile(TimestampedModel):
    """Settings for one account. The display name appears on certificates."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learner_profile"
    )
    display_name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.display_name or str(self.user)


class AchievementRecord(TimestampedModel):
    class AchievementType(models.TextChoices):
        PERSONAL_LEARNING_RECORD = "personal_learning_record", "Personal learning record"
        CUSTOM_CERTIFICATE = "custom_certificate", "Custom certificate"

    class CompletionBasis(models.TextChoices):
        SELF_ATTESTED = "self_attested", "Self-attested"
        EVIDENCE_DOCUMENTED = "evidence_documented", "Evidence documented"
        HUMAN_REVIEWED = (
            "human_reviewed",
            "Evidence documented, with human observation on some items",
        )

    # PROTECT: a record must not vanish silently if a plan is deleted.
    learning_plan = models.OneToOneField(
        LearningPlan, on_delete=models.PROTECT, related_name="achievement"
    )
    achievement_type = models.CharField(max_length=30, choices=AchievementType.choices)
    display_title = models.CharField(max_length=300)
    program_name = models.CharField(max_length=200)
    requirement_version_label = models.CharField(max_length=100)
    completed_at = models.DateTimeField()
    completion_basis = models.CharField(max_length=30, choices=CompletionBasis.choices)
    disclaimer_text_version = models.CharField(max_length=20)
    # Snapshots, so later edits do not change an issued record.
    learner_display_name = models.CharField(max_length=100)
    issuer_name = models.CharField(max_length=100)

    class Meta:
        ordering = ["-completed_at", "-id"]

    def __str__(self):
        return self.display_title

    def clean(self):
        if self.learning_plan_id and (
            self.learning_plan.status != LearningPlan.Status.PERSONALLY_COMPLETED
            and self.learning_plan.status != LearningPlan.Status.ARCHIVED
        ):
            raise ValidationError("A record needs a personally completed plan.")

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.clean()
        super().save(*args, **kwargs)
