"""How much of a program's catalog is validated. Business logic, no views.

An entry counts as validated only if its newest published version has a
reviewed or verified source status, a known rights status, and every
requirement node cites a source with a URL. Everything else is not validated.

A catalog may be called complete only if all of these hold:
- the owner set `catalog_validated_complete` on the program,
- the expected entry count is known,
- every entry is validated and the entry count equals the expected count.
The default is False.
"""
from dataclasses import dataclass
from typing import List, Optional

from django.db.models import Count, Q

from requirements.models import RequirementNode

from .models import Award, AwardVersion, Program

INCOMPLETE_MESSAGE = "Incomplete catalog coverage. Not every entry has been checked against its source."


@dataclass(frozen=True)
class ProgramCoverage:
    program_id: int
    program_name: str
    entries_known: int  # awards in the catalog (archived excluded)
    entries_validated: int  # published, reviewed, rights known, sources cited
    entries_unvalidated: int
    expected_total: Optional[int]  # None means unknown
    entries_unknown: Optional[int]  # expected minus known; None if expected is unknown
    complete: bool
    reasons: List[str]  # plain-language reasons the catalog is not complete

    @property
    def label(self):
        return "Complete (validated)" if self.complete else "Incomplete catalog coverage"


def _is_validated(version):
    if version is None:
        return False
    if version.source_status not in (
        AwardVersion.SourceStatus.REVIEWED,
        AwardVersion.SourceStatus.VERIFIED,
    ):
        return False
    if version.rights_status == AwardVersion.RightsStatus.UNKNOWN:
        return False
    counts = RequirementNode.objects.filter(award_version=version).aggregate(
        total=Count("pk"),
        cited=Count("pk", filter=~Q(source__isnull=True) & ~Q(source__url="")),
    )
    return counts["total"] > 0 and counts["total"] == counts["cited"]


def program_coverage(program):
    awards = program.awards.exclude(status=Award.Status.ARCHIVED)
    known = validated = 0
    for award in awards:
        known += 1
        latest = (
            award.versions.filter(status=AwardVersion.Status.PUBLISHED)
            .order_by("-published_at", "-pk")
            .first()
        )
        if _is_validated(latest):
            validated += 1
    expected = program.catalog_expected_count
    unvalidated = known - validated
    reasons = []
    if not program.catalog_validated_complete:
        reasons.append("The owner has not marked this catalog as validated.")
    if expected is None:
        reasons.append("The number of entries in the program is unknown.")
    elif known != expected:
        reasons.append(f"{known} of {expected} expected entries are in the catalog.")
    if unvalidated:
        reasons.append(f"{unvalidated} entries are not yet published and reviewed.")
    if known == 0:
        reasons.append("The catalog has no entries.")
    return ProgramCoverage(
        program_id=program.pk,
        program_name=program.name,
        entries_known=known,
        entries_validated=validated,
        entries_unvalidated=unvalidated,
        expected_total=expected,
        entries_unknown=None if expected is None else max(expected - known, 0),
        complete=not reasons,
        reasons=reasons,
    )


def catalog_may_be_called_complete(program):
    """True only when the catalog was explicitly validated. Default False."""
    return program_coverage(program).complete


def coverage_for_programs(programs=None):
    """Coverage for each program. Use in a view context, for example
    {"coverage": {c.program_id: c for c in coverage_for_programs()}}."""
    if programs is None:
        programs = Program.objects.all()
    return [program_coverage(p) for p in programs]
