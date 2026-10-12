"""Create the "How to use Merit Badge" tutorial as a published, custom program."""
from django.core.management.base import BaseCommand
from django.db import transaction

from programs import tutorial
from programs.models import AwardVersion
from requirements import services
from requirements.importer import commit_import


@transaction.atomic
def seed():
    """Return "created", "published" or "exists". Never changes a published version."""
    version = AwardVersion.objects.filter(
        award__program__owner__slug=tutorial.OWNER_SLUG,
        award__program__slug=tutorial.PROGRAM_SLUG,
        award__slug=tutorial.AWARD_SLUG,
        version_label=tutorial.LABEL,
    ).first()
    if version is not None and version.status not in (
        AwardVersion.Status.DRAFT,
        AwardVersion.Status.REVIEW,
    ):
        return "exists"
    outcome = "published"
    if version is None:
        version = commit_import(tutorial.tutorial_data())
        outcome = "created"
    if version.status == AwardVersion.Status.DRAFT:
        services.submit_for_review(version)
    services.publish_version(version)
    return outcome


class Command(BaseCommand):
    help = (
        "Create the project-authored tutorial 'How to use Merit Badge'. Safe to run again. "
        "Never changes a published version or your progress."
    )

    def handle(self, *args, **options):
        outcome = seed()
        messages = {
            "created": "Created and published the tutorial.",
            "published": "Published the tutorial.",
            "exists": "The tutorial already exists. Nothing changed.",
        }
        self.stdout.write(messages[outcome])
