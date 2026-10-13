"""AI tutoring records (PLAN.md 6.12).

Nothing here is evidence and nothing here changes progress. A session holds its
transcript only while it is open. After it ends, the learner keeps the summary,
keeps the summary and transcript, or discards the whole session.
"""
from django.conf import settings
from django.db import models

from learning.models import RequirementProgress


class AISettings(models.Model):
    """One row (pk=1). The API key is stored encrypted and is never shown."""

    enabled = models.BooleanField(default=False)
    base_url = models.CharField(max_length=500, blank=True)
    model = models.CharField(max_length=200, blank=True)
    api_key_encrypted = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI settings"
        verbose_name_plural = "AI settings"

    def __str__(self):
        return "AI settings"

    def __repr__(self):
        return "<AISettings enabled=%s>" % self.enabled


class TutoringSession(models.Model):
    class Mode(models.TextChoices):
        DISCUSS = "discuss", "Discuss"
        EXPLAIN = "explain", "Explain"
        PRACTICE = "practice", "Practice"
        CHECK = "check", "Check my understanding"
        PREPARE = "prepare", "Prepare to demonstrate"
        REVIEW = "review", "Review my evidence"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ENDED = "ended", "Ended, waiting for your choice"
        KEPT = "kept", "Kept"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutoring_sessions"
    )
    progress = models.ForeignKey(
        RequirementProgress, on_delete=models.CASCADE, related_name="tutoring_sessions"
    )
    mode = models.CharField(max_length=12, choices=Mode.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    provider_name = models.CharField(max_length=60)
    model_identifier = models.CharField(max_length=200, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True)
    # What the tutor was given: requirement and version, with origin. Not model output.
    source_references = models.JSONField(default=list, blank=True)
    # List of {"role": "user"|"assistant", "content": str}. Cleared unless the learner keeps it.
    transcript = models.JSONField(default=list, blank=True)
    transcript_saved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.get_mode_display()} / {self.progress}"
