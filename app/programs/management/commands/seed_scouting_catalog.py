"""Create the Scouting catalog structure. No requirement text, no awards."""
from django.core.management.base import BaseCommand
from django.db import transaction

from programs import scouting
from programs.models import Program, ProgramOwner


@transaction.atomic
def seed():
    """Create missing rows only. Never overwrites edits. Returns the number created."""
    created = 0
    owner, was_created = ProgramOwner.objects.get_or_create(
        slug=scouting.OWNER_SLUG,
        defaults={
            "name": scouting.OWNER_NAME,
            "owner_type": ProgramOwner.OwnerType.ORGANIZATION,
            "website_url": scouting.OWNER_URL,
            "description": scouting.OWNER_DESCRIPTION,
            "country_or_region": "US",
        },
    )
    created += was_created
    for spec in scouting.PROGRAMS:
        _, was_created = Program.objects.get_or_create(
            owner=owner,
            slug=spec.slug,
            defaults={
                "name": spec.name,
                "program_type": "scouting",
                "description": spec.description,
                "status": Program.Status.DRAFT,
                "is_custom": False,
                "visibility": Program.Visibility.ALL,
                "created_by": None,
                "catalog_source_url": spec.catalog_source_url,
                "catalog_expected_count": None,
                "catalog_validated_complete": False,
            },
        )
        created += was_created
    return created


class Command(BaseCommand):
    help = (
        "Create the Scouting America owner and the Cub Scouts and Scouts BSA programs. "
        "Safe to run again. Adds no requirement text."
    )

    def handle(self, *args, **options):
        created = seed()
        self.stdout.write(f"Created {created} rows. Programs stay draft and unvalidated.")
