"""Scouting catalog structure: seed, provenance, coverage, generic engine."""
import io

import pytest
from django.core.management import call_command

from learning import completion as c
from programs import coverage, scouting
from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements.models import RequirementNode, SourceRecord
from requirements.tree_rules import NodeSpec

pytestmark = pytest.mark.django_db
DONE = "personally_completed"


def seed():
    call_command("seed_scouting_catalog", stdout=io.StringIO())


def test_seed_is_idempotent_and_keeps_edits():
    seed()
    Program.objects.filter(slug="scouts-bsa").update(catalog_expected_count=5)
    seed()
    assert ProgramOwner.objects.filter(slug="scouting-america").count() == 1
    assert Program.objects.count() == 2
    assert Program.objects.get(slug="scouts-bsa").catalog_expected_count == 5


def test_seed_ships_no_requirements_or_awards():
    seed()
    assert RequirementNode.objects.count() == 0
    assert Award.objects.count() == 0
    assert AwardVersion.objects.count() == 0


def test_provenance_and_no_recognition_claim():
    seed()
    owner = ProgramOwner.objects.get(slug="scouting-america")
    assert owner.website_url.startswith("https://")
    assert "not affiliated" in owner.description and "recognized" in owner.description
    for p in Program.objects.all():
        assert p.catalog_source_url.startswith("https://")
        assert p.status == Program.Status.DRAFT
        assert p.catalog_validated_complete is False
        assert p.catalog_expected_count is None
        assert not p.is_custom


def test_award_shapes_use_existing_types():
    types = {s.award_type for spec in scouting.PROGRAMS for s in spec.shapes}
    assert types == {"rank", "adventure", "merit_badge"}
    assert set(types) <= set(Award.AwardType.values)


def _entry(program, slug, *, status="draft", source_status="unverified",
           rights="unknown", cited=False):
    award = Award.objects.create(program=program, name=slug, slug=slug, award_type="merit_badge")
    v = AwardVersion.objects.create(
        award=award, version_label="v1", source_status=source_status, rights_status=rights
    )
    src = SourceRecord.objects.create(title="s", url="https://example.org/x") if cited else None
    RequirementNode.objects.create(award_version=v, text="x", source=src)
    if status == "published":
        v.status = AwardVersion.Status.REVIEW
        v.save()
        from requirements.services import publish_version
        try:
            publish_version(v)
        except Exception:
            AwardVersion.objects.filter(pk=v.pk).update(status="published")
    return v


def test_coverage_default_is_never_complete():
    seed()
    for p in Program.objects.all():
        cov = coverage.program_coverage(p)
        assert cov.complete is False
        assert not coverage.catalog_may_be_called_complete(p)
        assert cov.expected_total is None and cov.entries_unknown is None
        assert cov.label == "Incomplete catalog coverage"


def test_unreviewed_entries_are_not_validated():
    seed()
    p = Program.objects.get(slug="scouts-bsa")
    _entry(p, "a")
    cov = coverage.program_coverage(p)
    assert (cov.entries_known, cov.entries_validated, cov.entries_unvalidated) == (1, 0, 1)


def test_complete_needs_explicit_flag_count_and_validated_entries():
    seed()
    p = Program.objects.get(slug="scouts-bsa")
    _entry(p, "a", status="published", source_status="reviewed", rights="link_only", cited=True)
    cov = coverage.program_coverage(p)
    assert cov.entries_validated == 1 and not cov.complete
    p.catalog_expected_count = 1
    p.save()
    assert not coverage.catalog_may_be_called_complete(p)  # flag still off
    p.catalog_validated_complete = True
    p.save()
    assert coverage.catalog_may_be_called_complete(p)
    p.catalog_expected_count = 2
    p.save()
    cov = coverage.program_coverage(p)
    assert not cov.complete and cov.entries_unknown == 1


def S(key, parent=None, order=0, logic="single", count=None):
    return NodeSpec(key=key, parent_key=parent, sort_order=order, display_number=str(key),
                    completion_logic=logic, completion_count=count)


def test_shapes_work_with_generic_engine():
    # Merit badge: all of (req 1, any of 2a/2b, choose 2 of 3a/3b/3c).
    mb = [S("r", logic="all"), S("1", "r", 0), S("2", "r", 1, "any"), S("2a", "2", 0), S("2b", "2", 1),
          S("3", "r", 2, "choose_n", 2), S("3a", "3", 0), S("3b", "3", 1), S("3c", "3", 2)]
    assert c.evaluate(mb, {"1": DONE, "2b": DONE, "3a": DONE}).state == c.INCOMPLETE
    assert c.evaluate(mb, {"1": DONE, "2b": DONE, "3a": DONE, "3c": DONE}).state == c.COMPLETE
    # Rank: all of (required group, choose 1 elective).
    rank = [S("r", logic="all"), S("req", "r", 0, "all"), S("a", "req", 0), S("b", "req", 1),
            S("el", "r", 1, "choose_n", 1), S("e1", "el", 0), S("e2", "el", 1)]
    assert c.evaluate(rank, {"a": DONE, "b": DONE}).state == c.INCOMPLETE
    assert c.evaluate(rank, {"a": DONE, "b": DONE, "e2": DONE}).state == c.COMPLETE
    # Adventure: all.
    adv = [S("r", logic="all"), S("1", "r", 0), S("2", "r", 1)]
    assert c.evaluate(adv, {"1": DONE}).state == c.INCOMPLETE
    assert c.evaluate(adv, {"1": DONE, "2": DONE}).state == c.COMPLETE


def test_engine_has_no_scouting_branches():
    import inspect
    src = inspect.getsource(c).lower()
    for word in ("scout", "merit", "rank", "adventure", "eagle"):
        assert word not in src
