"""Evidence validation, storage, review status and authenticated downloads."""
import io
import os

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse

from evidence import services as ev
from evidence.models import EvidenceRecord
from evidence.storage import get_storage
from learning import services
from learning.models import RequirementProgress
from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements import services as req
from requirements.models import RequirementNode

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def private_storage(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "evidence": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "evidence")},
        },
    }
    return tmp_path / "evidence"


@pytest.fixture
def user():
    return get_user_model().objects.create_user("owner", password="pw")


@pytest.fixture
def other():
    return get_user_model().objects.create_user("other", password="pw")


@pytest.fixture
def progress(user):
    owner = ProgramOwner.objects.create(name="Me", slug="me", owner_type="individual")
    program = Program.objects.create(owner=owner, name="C", slug="c", is_custom=True, visibility="all")
    award = Award.objects.create(program=program, name="A", slug="a")
    v = AwardVersion.objects.create(award=award, version_label="1")
    RequirementNode.objects.create(award_version=v, display_number="1", text="t")
    req.submit_for_review(v)
    req.publish_version(v)
    plan = services.start_plan(services.create_plan(user, v))
    return RequirementProgress.objects.get(learning_plan=plan)


def upload(name="photo.png", data=PNG, content_type="image/png"):
    return SimpleUploadedFile(name, data, content_type=content_type)


# Validation ---------------------------------------------------------------------------

def test_valid_image_is_stored_privately(progress, user, private_storage):
    rec = ev.add_file_evidence(user, progress, upload(), title="My model")
    assert rec.evidence_type == "image" and rec.size_bytes == len(PNG)
    assert len(rec.sha256) == 64
    assert get_storage().exists(rec.storage_key)
    assert os.path.exists(private_storage / rec.storage_key)
    assert rec.storage_key.startswith(f"{user.pk}/{progress.learning_plan_id}/")


@pytest.mark.parametrize("name", ["run.exe", "page.html", "x.svg", "noext", "a.png.php", "evil.sh"])
def test_bad_extension_refused(progress, user, name):
    with pytest.raises(ev.EvidenceError):
        ev.add_file_evidence(user, progress, upload(name=name))
    assert not EvidenceRecord.objects.exists()


def test_oversize_refused(progress, user, settings):
    settings.EVIDENCE_MAX_UPLOAD_BYTES = 100
    with pytest.raises(ev.EvidenceError, match="too large"):
        ev.add_file_evidence(user, progress, upload(data=PNG + b"x" * 100))
    ev.add_file_evidence(user, progress, upload(data=PNG[:50]))


def test_empty_file_refused(progress, user):
    with pytest.raises(ev.EvidenceError):
        ev.add_file_evidence(user, progress, upload(data=b""))


def test_content_type_mismatch_refused(progress, user):
    with pytest.raises(ev.EvidenceError, match="does not match"):
        ev.add_file_evidence(user, progress, upload(content_type="text/html"))


def test_content_must_match_signature(progress, user):
    with pytest.raises(ev.EvidenceError, match="does not look like"):
        ev.add_file_evidence(user, progress, upload(data=b"<html>script</html>"))


def test_traversal_name_cannot_escape_storage(progress, user, private_storage):
    rec = ev.add_file_evidence(user, progress, upload(name="../../../etc/evil.png"))
    assert ".." not in rec.storage_key and "evil" not in rec.storage_key
    assert rec.original_filename == "evil.png"
    path = (private_storage / rec.storage_key).resolve()
    assert str(path).startswith(str(private_storage.resolve()))
    rec2 = ev.add_file_evidence(user, progress, upload(name="..\\..\\win.png"))
    assert rec2.original_filename == "win.png" and "\\" not in rec2.storage_key


def test_storage_is_not_under_static_root(settings):
    assert str(settings.STATIC_ROOT) not in settings.STORAGES["evidence"]["OPTIONS"]["location"]


def test_file_types_need_upload_service(progress, user):
    with pytest.raises(ev.EvidenceError):
        ev.add_text_evidence(user, progress, "image", title="x")


# Review status ---------------------------------------------------------------------------

def test_human_observed_needs_label(progress, user):
    rec = ev.add_text_evidence(user, progress, "witness_record", description="d")
    with pytest.raises(ev.EvidenceError):
        ev.record_human_observation(user, rec, reviewer_label="  ")
    rec.refresh_from_db()
    assert rec.review_status == "unreviewed"
    ev.record_human_observation(user, rec, reviewer_label="Coach Sam", notes="Watched it")
    rec.refresh_from_db()
    assert rec.review_status == "human_observed" and rec.reviewer_name_or_label == "Coach Sam"


def test_ai_summary_never_human_observed(progress, user):
    rec = ev.add_text_evidence(user, progress, "ai_practice_summary", description="d")
    with pytest.raises(ev.EvidenceError):
        ev.record_human_observation(user, rec, reviewer_label="Sam")
    rec.review_status = "human_observed"
    rec.reviewer_name_or_label = "Sam"
    with pytest.raises(ValidationError):
        rec.save()


def test_database_blocks_human_observed_without_label(progress, user):
    rec = ev.add_text_evidence(user, progress, "note", description="d")
    with pytest.raises((ValidationError, IntegrityError)):
        with transaction.atomic():
            rec.review_status = "human_observed"
            rec.save()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EvidenceRecord.objects.filter(pk=rec.pk).update(review_status="human_observed")


def test_new_evidence_is_unreviewed_and_attest_is_not_observation(progress, user):
    rec = ev.add_text_evidence(user, progress, "note", description="d")
    assert rec.review_status == "unreviewed"
    ev.attest_evidence(user, rec)
    assert rec.review_status == "learner_attested"
    ev.record_feedback(user, rec, reviewer_label="Mom", notes="Looks good")
    assert rec.review_status == "feedback_received"


# Permissions -------------------------------------------------------------------------------

def test_other_user_cannot_add_or_change_evidence(progress, user, other):
    with pytest.raises(PermissionDenied):
        ev.add_text_evidence(other, progress, "note", description="x")
    with pytest.raises(PermissionDenied):
        ev.add_file_evidence(other, progress, upload())
    rec = ev.add_text_evidence(user, progress, "note", description="x")
    for fn in (ev.attest_evidence, ev.delete_evidence):
        with pytest.raises(PermissionDenied):
            fn(other, rec)
    with pytest.raises(PermissionDenied):
        ev.record_human_observation(other, rec, reviewer_label="me")


def test_download_requires_login_and_ownership(client, progress, user, other):
    rec = ev.add_file_evidence(user, progress, upload(name="my pic.png"))
    url = reverse("evidence_download", args=[rec.pk])
    anon = client.get(url)
    assert anon.status_code == 302 and "login" in anon["Location"]
    client.force_login(other)
    assert client.get(url).status_code == 404
    client.force_login(user)
    resp = client.get(url)
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == PNG
    assert resp["Content-Disposition"].startswith("attachment")
    assert "no-store" in resp["Cache-Control"]


def test_no_evidence_route_under_static_or_media(client, progress, user):
    rec = ev.add_file_evidence(user, progress, upload())
    client.force_login(user)
    assert client.get("/media/" + rec.storage_key).status_code == 404
    assert client.get("/static/" + rec.storage_key).status_code == 404


def test_missing_file_gives_404(client, progress, user):
    rec = ev.add_file_evidence(user, progress, upload())
    get_storage().delete(rec.storage_key)
    client.force_login(user)
    assert client.get(reverse("evidence_download", args=[rec.pk])).status_code == 404


# Deletion -------------------------------------------------------------------------------------

def test_deletion_report_and_delete_removes_file(
    progress, user, django_capture_on_commit_callbacks
):
    rec = ev.add_file_evidence(user, progress, upload())
    ev.add_text_evidence(user, progress, "note", description="n")
    report = ev.deletion_report_for_progress(progress)
    assert (report.records, report.files, report.bytes) == (2, 1, len(PNG))
    assert "cannot be undone" in report.summary()
    assert EvidenceRecord.objects.count() == 2  # reporting changed nothing
    key = rec.storage_key
    with django_capture_on_commit_callbacks(execute=True):
        ev.delete_evidence(user, rec)
    assert not get_storage().exists(key)
    assert EvidenceRecord.objects.count() == 1


def test_cascade_delete_of_plan_removes_files(
    progress, user, django_capture_on_commit_callbacks
):
    rec = ev.add_file_evidence(user, progress, upload())
    key = rec.storage_key
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_plan(progress.learning_plan)
    assert not get_storage().exists(key)
