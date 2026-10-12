"""Scouting structure on the generic engine. Structure only, no requirement text.

Scouting concepts map onto ProgramOwner, Program, Award, AwardVersion and
RequirementNode. Nothing here decides completion. The generic engine in
learning/completion.py does that from each node's `completion_logic`.

Shapes describe how an entry is stored. They are guidance for authors and
importers, not rules the engine reads.
"""
from dataclasses import dataclass
from typing import Tuple

from .models import Award

OWNER_SLUG = "scouting-america"
OWNER_NAME = "Scouting America"
OWNER_URL = "https://www.scouting.org/"
# The app is not affiliated with, endorsed by or recognized by the owner.
OWNER_DESCRIPTION = (
    "Named as the source of Scouting program content. This app is unofficial. "
    "It is not affiliated with, endorsed by or recognized by Scouting America."
)

# Version label for entries that have no reviewed source yet.
UNREVIEWED_VERSION_LABEL = "unreviewed"


@dataclass(frozen=True)
class AwardShape:
    award_type: str
    label: str
    top_level_logic: str  # usual `completion_logic` of the root node
    structure: str  # plain-language note for authors
    categories: Tuple[str, ...] = ()  # optional values for Award.category


MERIT_BADGE = AwardShape(
    award_type=Award.AwardType.MERIT_BADGE,
    label="Merit badge",
    top_level_logic="all",
    structure="Numbered requirements. Alternatives use 'any' or 'choose_n' groups. "
    "Keep numbers such as 4a or 5b(2) in display_number.",
)
RANK = AwardShape(
    award_type=Award.AwardType.RANK,
    label="Rank",
    top_level_logic="all",
    structure="A group per area. Required adventures or merit badges are single "
    "nodes. Elective choices use 'choose_n'.",
)
ADVENTURE = AwardShape(
    award_type=Award.AwardType.ADVENTURE,
    label="Adventure",
    top_level_logic="all",
    structure="Numbered requirements. 'Do N of these' uses 'choose_n'. "
    "Set Award.category to the rank or den level.",
)


@dataclass(frozen=True)
class ProgramSpec:
    slug: str
    name: str
    description: str
    catalog_source_url: str
    shapes: Tuple[AwardShape, ...]


PROGRAMS = (
    ProgramSpec(
        slug="cub-scouts",
        name="Cub Scouts",
        description="Cub Scouts program structure. No requirement text is included.",
        catalog_source_url="https://www.scouting.org/programs/cub-scouts/",
        shapes=(RANK, ADVENTURE),
    ),
    ProgramSpec(
        slug="scouts-bsa",
        name="Scouts BSA",
        description="Scouts BSA program structure. No requirement text is included.",
        catalog_source_url="https://www.scouting.org/programs/scouts-bsa/",
        shapes=(RANK, MERIT_BADGE),
    ),
)


def shapes_for(program_slug):
    for spec in PROGRAMS:
        if spec.slug == program_slug:
            return spec.shapes
    return ()
