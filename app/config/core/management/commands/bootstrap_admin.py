"""Create the first (admin) user from environment variables, idempotently."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create a superuser from BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD "
        "(optional BOOTSTRAP_ADMIN_EMAIL). Does nothing if the user already exists."
    )

    def handle(self, *args, **options):
        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "")
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "")
        if not username or not password:
            raise CommandError("Set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD.")
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User '{username}' already exists; nothing to do.")
            return
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
