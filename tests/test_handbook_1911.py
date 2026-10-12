"""1911 Boy Scouts Handbook import: counts, schema, drafts only, idempotency, exact text."""
import json
import re
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from programs.coverage import program_coverage
from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements import importer
from requirements.models import RequirementNode, SourceRecord

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app/programs/data/handbook_1911"
SCHEMA = json.loads((ROOT / "docs/schemas/program-import.schema.json").read_text())

# Counted in the Project Gutenberg #29558 HTML: 57 centered bold badge headings
# between the {24} page marker and "Life Scout". Scholarship has only a printed
# NOTE and no requirements, so it is not imported. 56 badges are imported.
SOURCE_BADGE_COUNT = 56


def files():
    return sorted(DATA.glob("*.json"))


def run(*args):
    out = StringIO()
    call_command("import_handbook_1911", *args, stdout=out)
    return out.getvalue()


def check_against_schema(value, schema, defs, path="$"):
    """Small check for the schema keywords this schema uses."""
    if "$ref" in schema:
        schema = defs[schema["$ref"].split("/")[-1]]
    if "const" in schema:
        assert value == schema["const"], path
    if "enum" in schema:
        assert value in schema["enum"], path
    if "oneOf" in schema:
        ok = 0
        for option in schema["oneOf"]:
            try:
                check_against_schema(value, option, defs, path)
                ok += 1
            except AssertionError:
                pass
        assert ok == 1, path
        return
    kind = schema.get("type")
    if kind == "object":
        assert isinstance(value, dict), path
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            assert key in value, f"{path}.{key} missing"
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(props), f"{path}: extra {set(value) - set(props)}"
        for key, item in value.items():
            if key in props:
                check_against_schema(item, props[key], defs, f"{path}.{key}")
    elif kind == "array":
        assert isinstance(value, list), path
        assert len(value) >= schema.get("minItems", 0), path
        assert len(value) <= schema.get("maxItems", 10**9), path
        for i, item in enumerate(value):
            check_against_schema(item, schema.get("items", {}), defs, f"{path}[{i}]")
    elif kind == "string":
        assert isinstance(value, str), path
        assert len(value) >= schema.get("minLength", 0), path
        assert len(value) <= schema.get("maxLength", 10**9), path
        if "pattern" in schema:
            assert re.search(schema["pattern"], value), path


def test_badge_count_matches_source():
    assert len(files()) == SOURCE_BADGE_COUNT


def test_every_file_validates_against_schema_and_importer():
    for path in files():
        data = json.loads(path.read_text(encoding="utf-8"))
        check_against_schema(data, SCHEMA, SCHEMA["$defs"])
        _, report = importer.plan_import(path.read_bytes())
        assert report.errors == [], path.name


def test_provenance_and_rights_in_every_file():
    for path in files():
        data = json.loads(path.read_text(encoding="utf-8"))
        v, src = data["version"], data["sources"][0]
        assert v["status"] == "draft" and v["label"] == "1911 first edition"
        assert v["rights_status"] == "public_domain"
        assert v["source_checked_at"] and "2009-08-01" in v["change_summary"]
        assert "29558" in src["url"] and "1911 first edition" in src["license_or_permission_notes"]
        assert "not a current or official Scouting America requirement" in src["license_or_permission_notes"]
        assert "obsolete or unsafe" in data["award"]["description"]
        assert all(r["source"] == src["key"] for r in data["requirements"])


def test_dry_run_writes_nothing():
    out = run("--dry-run")
    assert "Dry run" in out and str(SOURCE_BADGE_COUNT) in out
    assert not Program.objects.exists() and not Award.objects.exists()
    assert not RequirementNode.objects.exists() and not SourceRecord.objects.exists()


def test_import_makes_drafts_only_and_is_idempotent():
    run()
    assert Award.objects.count() == SOURCE_BADGE_COUNT
    assert AwardVersion.objects.count() == SOURCE_BADGE_COUNT
    assert set(AwardVersion.objects.values_list("status", flat=True)) == {AwardVersion.Status.DRAFT}
    assert not AwardVersion.objects.filter(published_at__isnull=False).exists()
    program = Program.objects.get()
    assert program.name == "Boy Scouts Handbook 1911" and program.is_custom
    assert program.owner.name == "Boy Scouts of America (historical)"
    assert "obsolete or unsafe" in program.description
    nodes, sources = RequirementNode.objects.count(), SourceRecord.objects.count()
    out = run()
    assert "New or changed: 0" in out
    assert RequirementNode.objects.count() == nodes and SourceRecord.objects.count() == sources
    assert Award.objects.count() == SOURCE_BADGE_COUNT


def test_text_is_exact_for_first_and_last_badge():
    run()
    first = AwardVersion.objects.get(award__slug="agriculture")
    lines = list(first.nodes.order_by("sort_order").values_list("display_number", "text"))
    assert lines[0] == ("1", "State different tests with grains.")
    assert lines[1] == (
        "2",
        "Grow at least an acre of corn which produces 25 per cent. better than the general average.",
    )
    assert lines[-1] == (
        "8",
        "Have a knowledge of Campbell's Soil Culture principle, and a knowledge of dry farming and of irrigation farming.",
    )
    assert len(lines) == 8
    assert first.award.description.startswith("To obtain a merit badge for Agriculture a scout must")
    last = AwardVersion.objects.get(award__slug="taxidermy")
    assert list(last.nodes.order_by("sort_order").values_list("display_number", "text")) == [
        ("1", "Have a knowledge of the game laws of the state in which he lives."),
        ("2", "Preserve and mount the skin of a game bird, or animal, killed in season."),
        ("3", "Mount for a rug the pelt of some fur animal."),
    ]


def test_page_markers_are_removed_but_wording_is_kept():
    run()
    archery = AwardVersion.objects.get(award__slug="archery").nodes.get(display_number="2")
    assert archery.text == (
        "Make a total score of 350 with 60 shots in one or two meets, using standard four-foot "
        "target at forty yards or three-foot target at thirty yards."
    )
    assert not RequirementNode.objects.filter(text__regex=r"\{\d+\}").exists()


def test_scholarship_is_not_imported():
    run()
    assert not (DATA / "scholarship.json").exists()
    assert not Award.objects.filter(slug="scholarship").exists()


def test_not_in_scouting_catalog_coverage():
    call_command("seed_scouting_catalog", stdout=StringIO())
    scouting = {p.pk: program_coverage(p).entries_known for p in Program.objects.filter(owner__slug="scouting-america")}
    run()
    assert scouting  # the Scouting programs exist
    for p in Program.objects.filter(owner__slug="scouting-america"):
        assert program_coverage(p).entries_known == scouting[p.pk]
    assert not Program.objects.filter(owner__slug="scouting-america", slug="boy-scouts-handbook-1911").exists()
    handbook = Program.objects.get(slug="boy-scouts-handbook-1911")
    cov = program_coverage(handbook)
    assert not cov.complete and cov.entries_validated == 0 and cov.expected_total is None
    assert ProgramOwner.objects.get(slug="boy-scouts-of-america-historical") != ProgramOwner.objects.get(slug="scouting-america")
