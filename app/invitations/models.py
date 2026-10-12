from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Role


class Invitation(models.Model):
    """A single-use sign-up link. Only the SHA-256 hash of the token is stored."""

    token_hash = models.CharField(max_length=64, unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    label = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    @property
    def status(self):
        if self.used_at:
            return "used"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "active"

    def __str__(self):
        return f"Invitation {self.pk} ({self.role}, {self.status})"
