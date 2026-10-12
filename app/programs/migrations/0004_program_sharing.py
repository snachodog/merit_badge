import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def set_creators(apps, schema_editor):
    """User-authored programs (owner "self") go to the first admin, private.
    Seeded and imported system programs become visible to all."""
    Program = apps.get_model("programs", "Program")
    Profile = apps.get_model("accounts", "Profile")
    User = apps.get_model("auth", "User")
    admin = (
        User.objects.filter(profile__role="admin").order_by("pk").first()
        or User.objects.order_by("pk").first()
    )
    for p in Program.objects.select_related("owner"):
        if p.is_custom and p.owner.slug == "self" and admin is not None:
            p.created_by, p.visibility = admin, "private"
        else:
            p.created_by, p.visibility = None, "all"
        p.save(update_fields=["created_by", "visibility"])


class Migration(migrations.Migration):
    dependencies = [
        ("programs", "0003_program_catalog_coverage"),
        ("accounts", "0002_profiles_for_existing_users"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="program",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_programs", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="program",
            name="visibility",
            field=models.CharField(choices=[("private", "Private (only the creator)"), ("shared", "Shared with chosen users"), ("all", "Shared with all users")], default="private", max_length=20),
        ),
        migrations.CreateModel(
            name="ProgramShare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("program", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shares", to="programs.program")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="program_shares", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="programshare",
            constraint=models.UniqueConstraint(fields=("program", "user"), name="program_share_unique"),
        ),
        migrations.RunPython(set_creators, migrations.RunPython.noop),
    ]
