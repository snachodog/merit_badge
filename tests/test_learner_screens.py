"""Learner screens, forms, certificate, export and isolation (Phase 2 part B)."""
import io
import json
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from achievements.models import AchievementRecord
from achievements import disclaimer
from evidence import services as ev
from evidence.models import EvidenceRecord
from learning import services
from learning.models import LearningPlan, RequirementProgress
from programs.models import AwardVersion
from requirements import services as req
from requirements.models import RequirementNode

from test_learning import add, award, publish  # noqa: F401  (fixtures and helpers)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

pytestmark = pytest.mark.django_db
RS = RequirementProgress.Status
PS = LearningPlan.Status


@pytest.fixture(autouse=True)
def private_media(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "evidence": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "evidence")},
        },
    }


@pytest.fixture
def user():
    return get_user_model().objects.create_user("owner", password="pw-long-enough-1")


@pytest.fixture
def other():
    return get_user_model().objects.create_user("other", password="pw-long-enough-1")


@pytest.fixture
def logged(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def other_client(other):
    from django.test import Client
    c = Client()
    c.force_login(other)
    return c


@pytest.fixture
def plan_setup(user, award):
    """Active plan: 1 (read), 2 (demonstrate), 3 (log, in a choose-1 group with 4)."""
    v = AwardVersion.objects.create(award=award, version_label="v1")
    n1 = add(v, "1", order=0, tags=["read"])
    n2 = add(v, "2", order=1, tags=["demonstrate"])
    g = add(v, "3", order=2, logic="any")
    n3a = add(v, "3a", g, 0, tags=["log"])
    n3b = add(v, "3b", g, 1)
    publish(v)
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    prog = {n.display_number: RequirementProgress.objects.get(learning_plan=plan, requirement_node=n)
            for n in (n1, n2, g, n3a, n3b)}
    return plan, prog


def png(name="photo.png"):
    return SimpleUploadedFile(name, PNG, content_type="image/png")


# Scenario D --------------------------------------------------------------------------

def test_scenario_d_custom_achievement_end_to_end(logged, user):
    post = logged.post
    assert post(reverse("program_create"), {"name": "Home Skills", "description": "Mine"}).status_code == 302
    from programs.models import Program, Award
    program = Program.objects.get(name="Home Skills")
    post(reverse("award_create", args=[program.pk]),
         {"name": "Bread Baker", "award_type": "custom", "description": "Bake bread"})
    award = Award.objects.get(name="Bread Baker")
    post(reverse("version_create", args=[award.pk]), {
        "version_label": "v1", "source_status": "user_authored", "rights_status": "user_authored",
        "change_summary": "",
    })
    version = AwardVersion.objects.get(award=award)

    def node(text, number, logic="single", parent=None, tags=(), count=""):
        url = reverse("node_add", args=[version.pk])
        if parent:
            url += f"?parent={parent.pk}"
        r = post(url, {
            "display_number": number, "node_type": "atomic", "text": text,
            "text_origin": "user_provided", "completion_logic": logic,
            "completion_count": count, "action_tags": list(tags),
        })
        assert r.status_code == 302, r.content
        return RequirementNode.objects.get(award_version=version, display_number=number)

    top = node("Make the dough.", "1", logic="all")
    a = node("Mix the ingredients.", "1a", parent=top, tags=["make"])
    b = node("Let it rise.", "1b", parent=top)
    c = node("Bake a loaf.", "2", tags=["demonstrate"])

    post(reverse("version_action", args=[version.pk, "submit"]))
    post(reverse("version_action", args=[version.pk, "publish"]))
    version.refresh_from_db()
    assert version.status == "published"

    # The version page offers Start plan; the start page shows requirements first.
    assert "Start plan" in logged.get(reverse("version_detail", args=[version.pk])).content.decode()
    page = logged.get(reverse("plan_start", args=[version.pk])).content.decode()
    assert page.index("Bake a loaf.") < page.index('id="start-h"')
    r = post(reverse("plan_start", args=[version.pk]), {"title_override": ""})
    plan = LearningPlan.objects.get(user=user)
    assert r.status_code == 302 and plan.status == PS.ACTIVE

    # Completion is blocked while required items are open.
    r = post(reverse("plan_complete", args=[plan.pk]), follow=True)
    assert not AchievementRecord.objects.exists()
    assert "not satisfied" in r.content.decode()
    assert "Review and complete" in logged.get(reverse("plan_detail", args=[plan.pk])).content.decode()

    def prog(n):
        return RequirementProgress.objects.get(learning_plan=plan, requirement_node=n)

    # Complete each leaf by the rules: evidence or attestation, then status.
    for n in (a, c):
        post(reverse("progress_attest", args=[prog(n).pk]), {"attested": "1"})
    post(reverse("evidence_add", args=[prog(c).pk, "file"]), {"file": png(), "title": "Loaf"})
    for n in (a, b, c):
        r = post(reverse("progress_status", args=[prog(n).pk]), {"status": "personally_completed"})
        assert r.status_code == 302
        assert prog(n).status == RS.PERSONALLY_COMPLETED

    page = logged.get(reverse("plan_complete", args=[plan.pk])).content.decode()
    assert "Record personal completion" in page
    r = post(reverse("plan_complete", args=[plan.pk]))
    assert r.status_code == 302
    plan.refresh_from_db()
    assert plan.status == PS.PERSONALLY_COMPLETED
    rec = AchievementRecord.objects.get(learning_plan=plan)
    assert rec.achievement_type == "custom_certificate"
    assert rec.completion_basis == "evidence_documented"

    html = logged.get(reverse("certificate", args=[rec.pk])).content.decode()
    assert "owner" in html  # username fallback when no display name
    assert "Bread Baker" in html and "Home Skills" in html and "v1" in html
    assert plan.personal_completed_at.strftime("%Y-%m-%d") in html
    assert "Merit Badge" in html
    assert disclaimer.disclaimer_text(rec.disclaimer_text_version, "Merit Badge") in html
    assert "does not confer an official award" in html
    assert "Not an official award" in html


# Prior knowledge, completion rules -------------------------------------------------------

def test_prior_knowledge_does_not_complete(logged, plan_setup):
    plan, prog = plan_setup
    p = prog["1"]
    r = logged.post(reverse("progress_prior", args=[p.pk]),
                    {"prior_knowledge_claim": "on", "prior_work_notes": "I read this as a kid."},
                    follow=True)
    p.refresh_from_db()
    assert p.prior_knowledge_claim and p.prior_work_notes == "I read this as a kid."
    assert p.status == RS.NOT_STARTED
    assert "did not complete the requirement" in r.content.decode()
    page = logged.get(reverse("progress_detail", args=[p.pk])).content.decode()
    assert "does not complete the requirement" in page


def test_status_error_is_visible(logged, plan_setup):
    plan, prog = plan_setup
    r = logged.post(reverse("progress_status", args=[prog["2"].pk]),
                    {"status": "personally_completed"}, follow=True)
    html = r.content.decode()
    assert 'role="alert"' in html and "demonstrate" in html
    prog["2"].refresh_from_db()
    assert prog["2"].status == RS.NOT_STARTED


def test_completion_blocked_while_mandatory_item_outstanding(logged, plan_setup):
    plan, prog = plan_setup
    for key in ("1", "3b"):
        services.set_progress_status(prog[key], RS.PERSONALLY_COMPLETED)
    html = logged.get(reverse("plan_detail", args=[plan.pk])).content.decode()
    assert "Still outstanding" in html and "not yet personally completed" in html
    logged.post(reverse("plan_complete", args=[plan.pk]))
    plan.refresh_from_db()
    assert plan.status == PS.ACTIVE and not AchievementRecord.objects.exists()
    r = logged.get(reverse("plan_complete", args=[plan.pk]))
    assert "You cannot record completion yet" in r.content.decode()


def test_requirement_page_sections_and_tag_guidance(logged, plan_setup):
    plan, prog = plan_setup
    html = logged.get(reverse("progress_detail", args=[prog["2"].pk])).content.decode()
    for h in ("1. Requirement text", "2. Interpretation", "3. Learn",
              "4. Demonstrate or complete", "5. Evidence and notes", "6. Progress"):
        assert h in html
    assert "A text answer alone is not a demonstration" in html
    assert "Explanatory, not official" in html
    assert "Not official text" not in html


def test_interview_guidance_rejects_ai_chat(logged, user, award):
    v = AwardVersion.objects.create(award=award, version_label="i1")
    n = add(v, "1", tags=["interview"])
    publish(v)
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    p = RequirementProgress.objects.get(learning_plan=plan)
    html = logged.get(reverse("progress_detail", args=[p.pk])).content.decode()
    assert "An AI chat is not an interview" in html


def test_time_log_entries_for_log_tag(logged, plan_setup):
    plan, prog = plan_setup
    p = prog["3a"]
    page = logged.get(reverse("progress_detail", args=[p.pk])).content.decode()
    assert "Add a time log entry" in page
    for minutes in ("20", "35"):
        r = logged.post(reverse("evidence_add", args=[p.pk, "timelog"]),
                        {"date": "2026-01-02", "minutes": minutes, "note": "worked"})
        assert r.status_code == 302
    entries = EvidenceRecord.objects.filter(progress=p, evidence_type="time_log")
    assert entries.count() == 2
    r = logged.post(reverse("evidence_add", args=[p.pk, "timelog"]),
                    {"date": "2026-01-02", "minutes": "0"})
    assert r.status_code == 200 and "errorlist" in r.content.decode()


def test_conditional_answer_via_screen(logged, user, award):
    v = AwardVersion.objects.create(award=award, version_label="c1")
    cond = add(v, "1", logic="conditional", cond={"key": "age", "equals": "10"})
    add(v, "1a", cond, 0)
    add(v, "2", order=1)
    publish(v)
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    html = logged.get(reverse("plan_detail", args=[plan.pk])).content.decode()
    assert "Questions that decide" in html and "need" in html
    logged.post(reverse("plan_condition", args=[plan.pk]), {"key": "age", "answer": "0"})
    plan.refresh_from_db()
    assert plan.condition_answers == {"age": "10"}
    logged.post(reverse("plan_condition", args=[plan.pk]), {"key": "age", "answer": "none"})
    plan.refresh_from_db()
    assert plan.condition_answers["age"] != "10"
    r = logged.post(reverse("plan_condition", args=[plan.pk]), {"key": "nope", "answer": "0"},
                    follow=True)
    assert 'role="alert"' in r.content.decode()


def test_plan_actions_and_errors(logged, plan_setup):
    plan, _ = plan_setup
    for action, expected in [("pause", PS.PAUSED), ("resume", PS.ACTIVE), ("abandon", PS.ABANDONED)]:
        logged.post(reverse("plan_action", args=[plan.pk, action]))
        plan.refresh_from_db()
        assert plan.status == expected
    r = logged.post(reverse("plan_action", args=[plan.pk, "pause"]), follow=True)
    assert 'role="alert"' in r.content.decode()  # abandoned cannot pause
    logged.post(reverse("plan_action", args=[plan.pk, "archive"]))
    plan.refresh_from_db()
    assert plan.status == PS.ARCHIVED


def test_overview_shows_counts_and_no_percentage(logged, plan_setup):
    plan, prog = plan_setup
    services.set_progress_status(prog["1"], RS.PERSONALLY_COMPLETED)
    html = logged.get(reverse("plan_detail", args=[plan.pk])).content.decode()
    assert "1 of 4 single requirements" in html
    assert "not a percentage" in html and "%" not in html.split("Where you stand")[1].split("Requirements</h2>")[0]
    assert "Completed personally" in html and "Not yet started" in html


def test_start_plan_refuses_unpublished(logged, award):
    v = AwardVersion.objects.create(award=award, version_label="d1")
    r = logged.post(reverse("plan_start", args=[v.pk]), follow=True)
    assert not LearningPlan.objects.exists()
    assert "published" in r.content.decode()


# Evidence forms --------------------------------------------------------------------------

def test_file_form_shows_privacy_notice_before_upload(logged, plan_setup):
    plan, prog = plan_setup
    html = logged.get(reverse("evidence_add", args=[prog["2"].pk, "file"])).content.decode()
    assert "no public web address" in html and "self-hosted" in html
    assert html.index("no public web address") < html.index('type="file"')
    assert 'enctype="multipart/form-data"' in html


def test_upload_note_link_and_bad_file(logged, plan_setup):
    plan, prog = plan_setup
    p = prog["2"]
    assert logged.post(reverse("evidence_add", args=[p.pk, "file"]), {"file": png()}).status_code == 302
    bad = SimpleUploadedFile("run.exe", b"MZ", content_type="application/octet-stream")
    r = logged.post(reverse("evidence_add", args=[p.pk, "file"]), {"file": bad})
    assert r.status_code == 200 and "not allowed" in r.content.decode()
    logged.post(reverse("evidence_add", args=[p.pk, "text"]),
                {"evidence_type": "note", "description": "I did it"})
    logged.post(reverse("evidence_add", args=[p.pk, "link"]), {"external_url": "https://example.org/x"})
    assert EvidenceRecord.objects.filter(progress=p).count() == 3
    p.refresh_from_db()
    assert p.status == RS.NOT_STARTED  # evidence alone does not complete


def test_delete_evidence_page_says_what_is_removed(logged, plan_setup):
    plan, prog = plan_setup
    rec = ev.add_file_evidence(plan.user, prog["2"], png(), title="Pic")
    page = logged.get(reverse("evidence_delete", args=[rec.pk])).content.decode()
    assert "1 evidence record(s) will be deleted" in page and "1 stored file" in page
    assert EvidenceRecord.objects.filter(pk=rec.pk).exists()  # GET changes nothing
    logged.post(reverse("evidence_delete", args=[rec.pk]))
    assert not EvidenceRecord.objects.filter(pk=rec.pk).exists()


def test_human_observation_needs_label(logged, plan_setup):
    plan, prog = plan_setup
    rec = ev.add_text_evidence(plan.user, prog["2"], "note", description="x")
    url = reverse("evidence_observe", args=[rec.pk])
    r = logged.post(url, {"reviewer_label": "  ", "notes": "ok"})
    assert r.status_code == 200
    rec.refresh_from_db()
    assert rec.review_status != "human_observed"
    logged.post(url, {"reviewer_label": "Aunt Jo, nurse", "notes": "watched"})
    rec.refresh_from_db()
    assert rec.review_status == "human_observed" and rec.reviewer_name_or_label == "Aunt Jo, nurse"


def test_closed_plan_refuses_evidence(logged, plan_setup):
    plan, prog = plan_setup
    services.change_plan_status(plan, PS.ABANDONED)
    r = logged.post(reverse("evidence_add", args=[prog["2"].pk, "text"]),
                    {"evidence_type": "note", "description": "late"})
    assert "plan is closed" in r.content.decode()


# Achievements, certificate, settings ---------------------------------------------------------

@pytest.fixture
def completed(user, award):
    v = AwardVersion.objects.create(award=award, version_label="v9", effective_from="2020-01-01")
    n = add(v, "1")
    publish(v)
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    p = RequirementProgress.objects.get(learning_plan=plan)
    services.set_progress_status(p, RS.PERSONALLY_COMPLETED)
    services.complete_plan(plan)
    return plan


def test_record_created_only_on_completion(user, award):
    v = AwardVersion.objects.create(award=award, version_label="v8")
    add(v, "1")
    publish(v)
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    assert not AchievementRecord.objects.exists()
    with pytest.raises(Exception):
        AchievementRecord.objects.create(
            learning_plan=plan, achievement_type="custom_certificate", display_title="x",
            program_name="p", requirement_version_label="v8", completed_at="2026-01-01T00:00Z",
            completion_basis="self_attested", disclaimer_text_version="1",
            learner_display_name="n", issuer_name="i",
        )


def test_certificate_uses_display_name_and_dates(logged, completed):
    logged.post(reverse("settings"), {"display_name": "Pat Example"})
    from achievements import services as a
    assert a.display_name_for(completed.user) == "Pat Example"
    rec = AchievementRecord.objects.get()
    # The record keeps the name it was issued with.
    html = logged.get(reverse("certificate", args=[rec.pk])).content.decode()
    assert "owner" in html and "Pat Example" not in html
    assert "2020-01-01" in html and "date not known" in html
    assert "Bread" in html
    assert "window.print" in html


def test_disclaimer_is_versioned():
    assert disclaimer.CURRENT_VERSION in disclaimer.DISCLAIMERS
    with pytest.raises(KeyError):
        disclaimer.disclaimer_text("999", "x")


def test_achievement_list_and_display_name_first(logged, user, award):
    from achievements import services as a
    a.set_display_name(user, "Pat Example")
    v = AwardVersion.objects.create(award=award, version_label="v7")
    add(v, "1")
    publish(v)
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    services.set_progress_status(RequirementProgress.objects.get(learning_plan=plan), RS.PERSONALLY_COMPLETED)
    services.complete_plan(plan)
    html = logged.get(reverse("achievement_list")).content.decode()
    assert "Bread" in html and "unofficial" in html
    rec = AchievementRecord.objects.get()
    assert "Pat Example" in logged.get(reverse("certificate", args=[rec.pk])).content.decode()


def test_nav_has_new_destinations(logged):
    html = logged.get(reverse("home")).content.decode()
    for label in ("My Learning", "Achievements", "Settings"):
        assert label in html


# Export ---------------------------------------------------------------------------------------

def test_export_contents_and_isolation(logged, plan_setup, other, award, completed):
    plan, prog = plan_setup
    rec = ev.add_file_evidence(plan.user, prog["2"], png(), title="Pic")
    services.record_prior_knowledge(prog["1"], claim=True, notes="prior")
    services.save_learner_notes(prog["1"], "my note")
    # Another user's data that must never appear.
    v = AwardVersion.objects.create(award=award, version_label="secret")
    add(v, "1")
    publish(v)
    oplan = services.create_plan(other, v)
    services.start_plan(oplan)
    oprog = RequirementProgress.objects.get(learning_plan=oplan)
    ev.add_text_evidence(other, oprog, "note", description="OTHER-PRIVATE")
    services.save_learner_notes(oprog, "OTHER-NOTE")

    r = logged.get(reverse("export_json"))
    assert r.status_code == 200 and "attachment" in r["Content-Disposition"]
    raw = r.content.decode()
    assert "OTHER-PRIVATE" not in raw and "OTHER-NOTE" not in raw and "secret" not in raw
    data = json.loads(raw)
    assert data["format_version"] == "1.0" and data["account"]["username"] == "owner"
    plans = {p["id"]: p for p in data["learning_plans"]}
    assert set(plans) == {plan.pk, completed.pk}
    exported = plans[plan.pk]
    assert exported["version"]["version_label"] == "v1"
    reqs = {x["display_number"]: x for x in exported["requirements"]}
    assert reqs["1"]["prior_work_notes"] == "prior" and reqs["1"]["learner_notes"] == "my note"
    ev_item = reqs["2"]["evidence"][0]
    assert ev_item["file"]["sha256"] == rec.sha256 and ev_item["file"]["archive_path"].startswith("evidence/")
    assert len(data["achievements"]) == 1 and data["achievements"][0]["official"] is False
    assert exported["status_log"]


def test_evidence_zip_has_only_own_files(logged, plan_setup, other, award):
    plan, prog = plan_setup
    rec = ev.add_file_evidence(plan.user, prog["2"], png(), title="Pic")
    v = AwardVersion.objects.create(award=award, version_label="s2")
    add(v, "1")
    publish(v)
    oplan = services.create_plan(other, v)
    services.start_plan(oplan)
    orec = ev.add_file_evidence(other, RequirementProgress.objects.get(learning_plan=oplan),
                                SimpleUploadedFile("other.png", PNG + b"x", content_type="image/png"))
    r = logged.get(reverse("export_evidence_zip"))
    assert r.status_code == 200 and r["Content-Type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(b"".join(r.streaming_content)))
    names = zf.namelist()
    assert "manifest.json" in names
    files = [n for n in names if n.startswith("evidence/")]
    assert len(files) == 1 and files[0].split("/")[-1].startswith(f"{rec.pk}-")
    assert zf.read(files[0]) == PNG
    assert not any(f"{orec.pk}-other" in n for n in names)


# Isolation and anonymous access ---------------------------------------------------------------

def test_cross_user_views_are_404(other_client, plan_setup, completed):
    plan, prog = plan_setup
    rec = ev.add_file_evidence(plan.user, prog["2"], png(), title="Pic")
    ach = AchievementRecord.objects.get()
    p = prog["2"].pk
    gets = [
        reverse("plan_detail", args=[plan.pk]),
        reverse("plan_complete", args=[plan.pk]),
        reverse("progress_detail", args=[p]),
        reverse("evidence_add", args=[p, "text"]),
        reverse("evidence_add", args=[p, "file"]),
        reverse("evidence_add", args=[p, "timelog"]),
        reverse("evidence_delete", args=[rec.pk]),
        reverse("evidence_observe", args=[rec.pk]),
        reverse("evidence_download", args=[rec.pk]),
        reverse("certificate", args=[ach.pk]),
    ]
    for url in gets:
        assert other_client.get(url).status_code == 404, url
    posts = [
        reverse("plan_action", args=[plan.pk, "pause"]),
        reverse("plan_condition", args=[plan.pk]),
        reverse("progress_status", args=[p]),
        reverse("progress_prior", args=[p]),
        reverse("progress_notes", args=[p]),
        reverse("progress_attest", args=[p]),
        reverse("evidence_delete", args=[rec.pk]),
        reverse("evidence_observe", args=[rec.pk]),
        reverse("plan_complete", args=[plan.pk]),
    ]
    for url in posts:
        assert other_client.post(url, {"status": "in_progress"}).status_code == 404, url
    plan.refresh_from_db()
    assert plan.status == PS.ACTIVE and EvidenceRecord.objects.filter(pk=rec.pk).exists()
    assert other_client.get(reverse("my_learning")).content.decode().count("Bread") == 0
    assert "Bread" not in other_client.get(reverse("achievement_list")).content.decode()


def test_anonymous_redirected_everywhere(client, plan_setup, completed):
    plan, prog = plan_setup
    rec = ev.add_file_evidence(plan.user, prog["2"], png())
    ach = AchievementRecord.objects.get()
    urls = [
        reverse("my_learning"), reverse("plan_start", args=[plan.award_version_id]),
        reverse("plan_detail", args=[plan.pk]), reverse("plan_complete", args=[plan.pk]),
        reverse("progress_detail", args=[prog["2"].pk]),
        reverse("evidence_add", args=[prog["2"].pk, "text"]),
        reverse("evidence_delete", args=[rec.pk]), reverse("evidence_observe", args=[rec.pk]),
        reverse("achievement_list"), reverse("certificate", args=[ach.pk]),
        reverse("settings"), reverse("export_json"), reverse("export_evidence_zip"),
    ]
    for url in urls:
        r = client.get(url)
        assert r.status_code == 302 and r["Location"].startswith("/accounts/login/"), url
    for url in [reverse("plan_action", args=[plan.pk, "pause"]), reverse("progress_status", args=[prog["2"].pk])]:
        r = client.post(url)
        assert r.status_code == 302 and r["Location"].startswith("/accounts/login/"), url
