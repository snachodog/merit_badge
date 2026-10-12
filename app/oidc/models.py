from django.conf import settings
from django.db import models


class OIDCSettings(models.Model):
    """One row (pk=1). The client secret is stored encrypted and is never shown."""

    enabled = models.BooleanField(default=False)
    issuer_url = models.CharField(max_length=500, blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    client_secret_encrypted = models.TextField(blank=True)
    scopes = models.CharField(max_length=255, default="openid email profile")
    button_label = models.CharField(max_length=60, default="Sign in with OIDC")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "OIDC settings"
        verbose_name_plural = "OIDC settings"

    def __str__(self):
        return "OIDC settings"

    def __repr__(self):
        return "<OIDCSettings enabled=%s>" % self.enabled


class OIDCIdentity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oidc_identities")
    issuer = models.CharField(max_length=500)
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issuer", "subject"], name="oidc_identity_issuer_subject_uniq"),
            models.UniqueConstraint(fields=["user", "issuer"], name="oidc_identity_user_issuer_uniq"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.issuer}"
