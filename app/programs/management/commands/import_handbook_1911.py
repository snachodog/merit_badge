"""Import every merit badge from the 1911 Boy Scouts Handbook as a draft version.

The files are in programs/data/handbook_1911 (one program-import file per badge).
This command never publishes. Run it again safely: unchanged badges are skipped.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from requirements import importer

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "handbook_1911"


class Command(BaseCommand):
    help = (
        "Import the 1911 Boy Scouts Handbook merit badges as draft versions. "
        "Use --dry-run to check the files and change nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Check the files; change nothing.")

    def handle(self, *args, dry_run, **options):
        files = sorted(DATA_DIR.glob("*.json"))
        if not files:
            raise CommandError(f"No badge files found in {DATA_DIR}.")
        planned = []
        problems = []
        for path in files:
            data, report = importer.plan_import(path.read_bytes())
            if report.errors or report.conflicts:
                for place, message in report.errors:
                    problems.append(f"{path.name}: {place or '(file)'}: {message}")
                problems.extend(f"{path.name}: {c}" for c in report.conflicts)
            planned.append((path, data, report))
        if problems:
            raise CommandError("Nothing was imported.\n" + "\n".join(problems))

        new = sum(1 for _, _, r in planned if not r.unchanged)
        same = len(planned) - new
        self.stdout.write(f"Badges in the source files: {len(planned)}. New or changed: {new}. Unchanged: {same}.")
        if dry_run:
            self.stdout.write("Dry run: nothing was changed.")
            return
        with transaction.atomic():
            for path, data, report in planned:
                if not report.unchanged:
                    importer.commit_import(data)
        self.stdout.write(
            self.style.SUCCESS(f"Imported {new} draft version(s). Nothing was published. Review them before you publish.")
        )
