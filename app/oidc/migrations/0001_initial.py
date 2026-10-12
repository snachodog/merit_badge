import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="OIDCSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("issuer_url", models.CharField(blank=True, max_length=500)),
                ("client_id", models.CharField(blank=True, max_length=255)),
                ("client_secret_encrypted", models.TextField(blank=True)),
                ("scopes", models.CharField(default="openid email profile", max_length=255)),
                ("button_label", models.CharField(default="Sign in with OIDC", max_length=60)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "OIDC settings", "verbose_name_plural": "OIDC settings"},
        ),
        migrations.CreateModel(
            name="OIDCIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issuer", models.CharField(max_length=500)),
                ("subject", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="oidc_identities", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("issuer", "subject"), name="oidc_identity_issuer_subject_uniq"),
                    models.UniqueConstraint(fields=("user", "issuer"), name="oidc_identity_user_issuer_uniq"),
                ],
            },
        ),
    ]
