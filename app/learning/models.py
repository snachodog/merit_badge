"""A learner's plan and per-requirement progress.

Definitions (AwardVersion, RequirementNode) are never changed by progress.
A plan is pinned to one published version for its whole life (PLAN.md 6.8).
Completion of groups and of the plan is derived by `completion.evaluate`.
Nothing here stores a percentage.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from programs.models import AwardVersion, TimestampedModel
from requirements.models import RequirementNode


class LearningPlan(TimestampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        PERSONALLY_COMPLETED = "personally_completed", "Personally completed"
        ABANDONED = "abandoned", "Abandoned"
        ARCHIVED = "archived", "Archived"

    # Allowed plan status changes. Completion also needs the engine (see services).
    TRANSITIONS = {
        Status.PLANNED: {Status.ACTIVE, Status.ABANDONED},
        Status.ACTIVE: {Status.PAUSED, Status.PERSONALLY_COMPLETED, Status.ABANDONED},
        Status.PAUSED: {Status.ACTIVE, Status.ABANDONED},
        Status.PERSONALLY_COMPLETED: {Status.ARCHIVED},
        Status.ABANDONED: {Status.ACTIVE, Status.ARCHIVED},
        Status.ARCHIVED: set(),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_plans"
    )
    award_version = models.ForeignKey(
        AwardVersion, on_delete=models.PROTECT, related_name="learning_plans"
    )
    title_override = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PLANNED)
    started_at = models.DateTimeField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    personal_completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # Learner answers to the conditions of conditional requirements: {"key": value}.
    condition_answers = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return self.title

    @property
    def title(self):
        return self.title_override or str(self.award_version.award)

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.award_version.status != AwardVersion.Status.PUBLISHED:
                raise ValidationError(
                    {"award_version": "A plan can only start from a published version."}
                )
        else:
            old = LearningPlan.objects.filter(pk=self.pk).values_list(
                "award_version_id", flat=True
            ).first()
            if old is not None and old != self.award_version_id:
                raise ValidationError(
                    {"award_version": "A plan stays on the version it started with."}
                )
        super().save(*args, **kwargs)


class PlanStatusLog(models.Model):
    """One row for every plan status change, including the first one."""

    plan = models.ForeignKey(LearningPlan, on_delete=models.CASCADE, related_name="status_log")
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, choices=LearningPlan.Status.choices)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["changed_at", "id"]

    def __str__(self):
        return f"{self.plan_id}: {self.from_status or '-'} -> {self.to_status}"


class RequirementProgress(TimestampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        AWAITING_EVIDENCE = "awaiting_evidence", "Awaiting evidence"
        READY_FOR_REVIEW = "ready_for_review", "Ready for review"
        PERSONALLY_COMPLETED = "personally_completed", "Personally completed"
        NEEDS_MORE_WORK = "needs_more_work", "Needs more work"
        NOT_APPLICABLE = "not_applicable_by_explicit_rule", "Not applicable by explicit rule"

    learning_plan = models.ForeignKey(
        LearningPlan, on_delete=models.CASCADE, related_name="progress"
    )
    requirement_node = models.ForeignKey(
        RequirementNode, on_delete=models.PROTECT, related_name="progress_rows"
    )
    status = models.CharField(
        max_length=40, choices=Status.choices, default=Status.NOT_STARTED
    )
    # A claim, nothing more. It never changes the status (PLAN.md 4.1 and 7.2).
    prior_knowledge_claim = models.BooleanField(default=False)
    prior_work_notes = models.TextField(blank=True)
    learner_notes = models.TextField(blank=True)
    self_attested_at = models.DateTimeField(null=True, blank=True)
    personally_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["learning_plan", "requirement_node"]
        constraints = [
            models.UniqueConstraint(
                fields=["learning_plan", "requirement_node"], name="progress_unique_node_per_plan"
            )
        ]

    def __str__(self):
        return f"{self.requirement_node} [{self.status}]"

    def clean(self):
        if (
            self.learning_plan_id
            and self.requirement_node_id
            and self.requirement_node.award_version_id != self.learning_plan.award_version_id
        ):
            raise ValidationError(
                {"requirement_node": "The requirement must belong to the plan's version."}
            )

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.clean()
        super().save(*args, **kwargs)
