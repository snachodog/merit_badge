from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    USER = "user", "User"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} ({self.role})"


class AuditRecord(models.Model):
    """Account event log (PLAN 6.14). Rows survive deletion of the users they mention."""

    event = models.CharField(max_length=60, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_label = models.CharField(max_length=150, blank=True)
    target_label = models.CharField(max_length=150, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.event} at {self.created_at:%Y-%m-%d %H:%M}"
