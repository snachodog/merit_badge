"""Create the first (admin) user from environment variables, idempotently."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create a superuser from BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD "
        "(optional BOOTSTRAP_ADMIN_EMAIL). Does nothing if the user already exists."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Set the password of an existing user to BOOTSTRAP_ADMIN_PASSWORD.",
        )

    def handle(self, *args, **options):
        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "")
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "")
        if not username or not password:
            raise CommandError("Set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD.")
        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing:
            from accounts.models import Role
            from accounts.services import ensure_profile

            ensure_profile(existing)
            if options["reset_password"]:
                existing.set_password(password)
                existing.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS(f"Password reset for '{username}'."))
            else:
                self.stdout.write(
                    f"User '{username}' already exists. The password was not changed. "
                    "Add --reset-password to set it from BOOTSTRAP_ADMIN_PASSWORD."
                )
            return
        user = User.objects.create_superuser(username=username, email=email, password=password)
        from accounts.models import Role
        from accounts.services import ensure_profile, set_role

        ensure_profile(user)
        set_role(None, user, Role.ADMIN)
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
