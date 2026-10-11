"""JSON import: validation paths, dry run, idempotency, drafts only."""
import copy
import io
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements import importer, services
from requirements.models import ImportRecord, RequirementActionTag, RequirementNode, SourceRecord

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs/schemas/examples/custom-example.json"
SCHEMA = ROOT / "docs/schemas/program-import.schema.json"


def base():
    return {
        "schema_version": "1.0",
        "program": {"slug": "p", "name": "P", "owner": "self"},
        "award": {"slug": "a", "name": "A"},
        "version": {"label": "v1", "source_status": "unverified", "rights_status": "user_authored"},
        "requirements": [
            {"display_number": "1", "text": "One."},
            {"display_number": "2", "text": "Two.", "children": [
                {"display_number": "2a", "text": "Two A.", "action_tags": ["make"]},
            ]},
        ],
    }


def paths(report):
    return {p for p, _ in report.errors}


def counts():
    return (Program.objects.count(), Award.objects.count(), AwardVersion.objects.count(),
            RequirementNode.objects.count(), ImportRecord.objects.count(), ProgramOwner.objects.count())


# Validation -------------------------------------------------------------------

def test_example_file_is_valid():
    data, report = importer.plan_import(EXAMPLE.read_bytes())
    assert report.errors == [] and report.can_commit and report.node_count == 7


def test_schema_enums_match_models():
    schema = json.loads(SCHEMA.read_text())
    node = schema["$defs"]["node"]["properties"]
    assert node["action_tags"]["items"]["enum"] == importer.ACTION_TAGS
    assert node["completion_logic"]["enum"] == importer.LOGIC_TYPES
    assert node["text_origin"]["enum"] == importer.TEXT_ORIGINS
    assert node["node_type"]["enum"] == importer.NODE_TYPES
    v = schema["properties"]["version"]["properties"]
    assert v["source_status"]["enum"] == importer.SOURCE_STATUSES
    assert v["rights_status"]["enum"] == importer.RIGHTS_STATUSES
    assert schema["properties"]["award"]["properties"]["award_type"]["enum"] == importer.AWARD_TYPES


def test_precise_error_paths():
    data = base()
    data["requirements"][1]["children"][0]["text"] = ""
    data["requirements"][1]["children"][0]["action_tags"] = ["bogus"]
    data["requirements"][0]["completion_logic"] = "choose_n"
    data["requirements"][0]["surprise"] = 1
    data["award"]["name"] = 5
    data["version"]["status"] = "published"
    _, report = importer.plan_import(data)
    got = paths(report)
    assert "requirements[1].children[0].text" in got
    assert "requirements[1].children[0].action_tags[0]" in got
    assert "requirements[0].surprise" in got
    assert "award.name" in got
    assert "version.status" in got
    assert not report.can_commit


def test_tree_rule_errors_use_paths():
    data = base()
    data["requirements"][0].update(completion_logic="choose_n", completion_count=3)
    data["requirements"][0]["children"] = [{"text": "x"}]
    data["requirements"][1]["completion_logic"] = "single"
    _, report = importer.plan_import(data)
    errs = dict(report.errors)
    assert "only 1 children" in errs["requirements[0]"]
    assert "cannot have child" in errs["requirements[1]"]


def test_missing_required_and_wrong_types():
    _, report = importer.plan_import({"schema_version": "2.0", "requirements": "no"})
    assert {"schema_version", "program", "award", "version"} <= paths(report)
    _, report = importer.plan_import([1, 2])
    assert paths(report) == {""}


@pytest.mark.parametrize("raw", [b"{not json", b"\xff\xfe\x00", b'{"a": 1, "a": 2}', b'{"a": NaN}'])
def test_bad_files_rejected(raw):
    data, report = importer.plan_import(raw)
    assert data is None and report.errors


def test_size_depth_and_count_limits():
    big = b" " * (importer.MAX_BYTES + 1)
    assert importer.plan_import(big)[1].errors
    data = base()
    node = data["requirements"][0]
    for _ in range(importer.MAX_DEPTH + 1):
        node["children"] = [{"text": "x"}]
        node = node["children"][0]
    assert any("nested more than" in m for _, m in importer.plan_import(data)[1].errors)
    data = base()
    data["requirements"] = [{"text": "x"} for _ in range(importer.MAX_NODES + 1)]
    assert any("more than" in m for _, m in importer.plan_import(data)[1].errors)


def test_official_source_needs_source_and_rights_or_unverified():
    data = base()
    data["requirements"][0]["text_origin"] = "official_source"
    data["version"]["source_status"] = "reviewed"
    data["version"]["rights_status"] = "unknown"
    _, report = importer.plan_import(data)
    assert {"version.source_status", "version.rights_status"} <= paths(report)
    data["version"]["source_status"] = "unverified"
    assert importer.plan_import(data)[1].errors == []
    data["version"]["source_status"] = "reviewed"
    data["version"]["rights_status"] = "licensed"
    data["sources"] = [{"key": "s", "title": "T"}]
    data["requirements"][0]["source"] = "s"
    assert importer.plan_import(data)[1].errors == []
    data["requirements"][0]["source"] = "missing"
    assert "requirements[0].source" in paths(importer.plan_import(data)[1])


def test_plan_example_fields_are_accepted_with_warning():
    data = base()
    data["requirements"][0]["evidence_expectations"] = ["log"]
    data["requirements"][0]["constraints"] = {"minimum_occurrences": 4}
    _, report = importer.plan_import(data)
    assert report.errors == [] and report.warnings


# Dry run and commit -----------------------------------------------------------

def test_dry_run_changes_nothing():
    before = counts()
    _, report = importer.plan_import(base())
    assert report.can_commit and report.creates
    assert counts() == before


def test_commit_creates_draft_with_tree_and_tags():
    version = importer.commit_import(base())
    assert version.status == "draft"
    assert [(n.display_number, d) for n, d in services.iter_tree(version)] == [("1", 0), ("2", 0), ("2a", 1)]
    node = RequirementNode.objects.get(display_number="2a")
    assert node.parent.display_number == "2" and node.parent.completion_logic == "all"
    tag = RequirementActionTag.objects.get()
    assert tag.tag == "make" and tag.reviewed is False
    assert version.award.program.owner.slug == "self" and ImportRecord.objects.count() == 1


def test_file_cannot_publish_directly():
    data = base()
    data["version"]["status"] = "published"
    with pytest.raises(importer.ImportRefused):
        importer.commit_import(data)
    assert AwardVersion.objects.count() == 0


def test_duplicate_import_is_a_no_op():
    importer.commit_import(base())
    before = counts()
    _, report = importer.plan_import(base())
    assert report.unchanged and not report.can_commit
    with pytest.raises(importer.ImportRefused):
        importer.commit_import(base())
    assert counts() == before


def test_changed_file_updates_the_draft_in_place():
    first = importer.commit_import(base())
    data = base()
    data["requirements"][0]["text"] = "One, changed."
    _, report = importer.plan_import(data)
    assert report.updates and report.can_commit
    second = importer.commit_import(data)
    assert second.pk == first.pk and AwardVersion.objects.count() == 1
    assert RequirementNode.objects.get(display_number="1").text == "One, changed."
    assert RequirementNode.objects.count() == 3


def test_published_version_is_never_overwritten():
    version = importer.commit_import(base())
    services.submit_for_review(version)
    services.publish_version(version)
    data = base()
    data["requirements"][0]["text"] = "Sneaky change."
    _, report = importer.plan_import(data)
    assert report.conflicts and not report.can_commit
    with pytest.raises(importer.ImportRefused):
        importer.commit_import(data)
    assert RequirementNode.objects.get(display_number="1").text == "One."


def test_existing_version_label_without_key_is_a_conflict():
    importer.commit_import(base())
    other = base()
    other["import_key"] = "another-key"
    _, report = importer.plan_import(other)
    assert report.conflicts
    other["version"]["label"] = "v2"
    assert importer.plan_import(other)[1].can_commit
    version = importer.commit_import(other)
    assert version.award.versions.count() == 2 and Award.objects.count() == 1


def test_failed_commit_rolls_back(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(importer, "_create_nodes", boom)
    with pytest.raises(RuntimeError):
        importer.commit_import(base())
    assert counts() == (0, 0, 0, 0, 0, 0)


# Command and upload page --------------------------------------------------------

def test_command_dry_run_and_import(tmp_path):
    out = io.StringIO()
    call_command("import_program", str(EXAMPLE), "--dry-run", stdout=out)
    assert "Dry run" in out.getvalue() and AwardVersion.objects.count() == 0
    call_command("import_program", str(EXAMPLE), stdout=out)
    assert AwardVersion.objects.get().status == "draft"
    call_command("import_program", str(EXAMPLE), stdout=out)  # repeat: no change
    assert AwardVersion.objects.count() == 1
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "1.0"}')
    with pytest.raises(CommandError):
        call_command("import_program", str(bad), stdout=out)


@pytest.fixture
def logged(client):
    client.force_login(get_user_model().objects.create_user("me", password="pw-long-enough-1"))
    return client


def upload(client, payload, name="x.json"):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return client.post(reverse("import_program"), {"file": SimpleUploadedFile(name, payload)})


def test_upload_page_previews_then_commits(logged):
    r = upload(logged, json.dumps(base()).encode())
    assert r.status_code == 200 and b"ready to import" in r.content and b"Will create" in r.content
    assert AwardVersion.objects.count() == 0
    r = logged.post(reverse("import_program"), {"action": "commit"})
    version = AwardVersion.objects.get()
    assert r.url == reverse("version_edit", args=[version.pk]) and version.status == "draft"


def test_upload_page_shows_error_paths(logged):
    data = base()
    data["requirements"][1]["children"][0]["text"] = ""
    r = upload(logged, json.dumps(data).encode())
    assert r.status_code == 400 and b"requirements[1].children[0].text" in r.content
    assert b"Import as draft" not in r.content
    r = logged.post(reverse("import_program"), {"action": "commit"})
    assert r.status_code == 302 and AwardVersion.objects.count() == 0


def test_upload_too_large(logged):
    r = upload(logged, b" " * (importer.MAX_BYTES + 10))
    assert r.status_code == 400 and b"larger than" in r.content


def test_upload_requires_login(client):
    assert client.get(reverse("import_program")).status_code == 302
    assert client.post(reverse("import_program"), {"action": "commit"}).status_code == 302
