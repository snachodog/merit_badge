"""Import a program, award and draft requirement tree from a JSON file."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements import importer


def format_report(report):
    lines = [f"Import key: {report.import_key or '(not known)'}", f"Result: {report.outcome}"]
    for title, items in (
        ("Will create", report.creates),
        ("Will update", report.updates),
        ("Conflicts", report.conflicts),
        ("Warnings", report.warnings),
    ):
        if items:
            lines.append(f"{title}:")
            lines.extend(f"  - {i}" for i in items)
    if report.errors:
        lines.append("Errors:")
        lines.extend(f"  - {p or '(file)'}: {m}" for p, m in report.errors)
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Import a program JSON file as a draft version. Use --dry-run to preview only."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to the JSON file.")
        parser.add_argument("--dry-run", action="store_true", help="Check the file; change nothing.")

    def handle(self, *args, file, dry_run, **options):
        path = Path(file)
        try:
            if path.stat().st_size > importer.MAX_BYTES:
                raise CommandError(f"The file is larger than {importer.MAX_BYTES // 1024} KiB.")
            raw = path.read_bytes()
        except OSError as exc:
            raise CommandError(f"Cannot read {file}: {exc.strerror}") from exc
        data, report = importer.plan_import(raw)
        self.stdout.write(format_report(report))
        if report.errors or report.conflicts:
            raise CommandError("Nothing was imported.")
        if dry_run:
            self.stdout.write("Dry run: nothing was changed.")
            return
        if report.unchanged:
            return
        version = importer.commit_import(data)
        self.stdout.write(self.style.SUCCESS(f"Imported draft version {version.pk}: {version}."))
