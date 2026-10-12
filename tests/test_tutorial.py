"""The tutorial seed: idempotent, engine-driven, outside Scouting coverage."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from achievements.models import AchievementRecord
from learning import services
from learning.models import LearningPlan, RequirementProgress
from programs import tutorial
from programs.coverage import program_coverage
from programs.management.commands.seed_scouting_catalog import seed as seed_scouting
from programs.models import AwardVersion, Program
from requirements.models import RequirementNode

pytestmark = pytest.mark.django_db
RS = RequirementProgress.Status


def version():
    return AwardVersion.objects.get(
        award__slug=tutorial.AWARD_SLUG, version_label=tutorial.LABEL
    )


@pytest.fixture
def user():
    return get_user_model().objects.create_user("learner", password="x")


def test_seed_twice_makes_one_published_version():
    call_command("seed_tutorial")
    call_command("seed_tutorial")
    assert AwardVersion.objects.filter(award__slug=tutorial.AWARD_SLUG).count() == 1
    v = version()
    assert v.status == AwardVersion.Status.PUBLISHED
    assert v.award.program.is_custom
    assert v.source_status == AwardVersion.SourceStatus.USER_AUTHORED
    assert v.rights_status == AwardVersion.RightsStatus.USER_AUTHORED
    nodes = RequirementNode.objects.filter(award_version=v)
    assert nodes.count() == 10
    assert not nodes.filter(text_origin="official_source").exists()
    assert "https://github.com/snachodog/merit_badge" in nodes.get(display_number="10").text


def test_plan_flow_creates_record_through_engine(user):
    call_command("seed_tutorial")
    plan = services.create_plan(user, version())
    services.start_plan(plan)
    progress = list(plan.progress.all())
    assert len(progress) == 10
    with pytest.raises(services.LearningError):
        services.complete_plan(plan)
    assert not AchievementRecord.objects.exists()
    for p in progress:
        services.set_progress_status(p, RS.PERSONALLY_COMPLETED)
    services.complete_plan(plan)
    record = AchievementRecord.objects.get(learning_plan=plan)
    assert record.achievement_type == AchievementRecord.AchievementType.CUSTOM_CERTIFICATE


def test_excluded_from_scouting_coverage():
    seed_scouting()
    before = {p.slug: program_coverage(p) for p in Program.objects.filter(program_type="scouting")}
    call_command("seed_tutorial")
    program = version().award.program
    assert program.program_type != "scouting"
    assert program.catalog_expected_count is None
    after = {p.slug: program_coverage(p) for p in Program.objects.filter(program_type="scouting")}
    assert before == after
    assert all(c.entries_known == 0 for c in after.values())


def test_reseed_keeps_progress(user):
    call_command("seed_tutorial")
    plan = services.create_plan(user, version())
    services.start_plan(plan)
    first = plan.progress.first()
    services.save_learner_notes(first, "my note")
    services.set_progress_status(first, RS.PERSONALLY_COMPLETED)
    call_command("seed_tutorial")
    first.refresh_from_db()
    assert first.learner_notes == "my note"
    assert first.status == RS.PERSONALLY_COMPLETED
    assert LearningPlan.objects.count() == 1
    assert plan.progress.count() == 10


def test_home_links_to_tutorial(client, user):
    client.force_login(user)
    assert "seed_tutorial" in client.get("/").content.decode()
    call_command("seed_tutorial")
    assert "/learning/" in client.get("/").content.decode()


def test_seed_1_1_alongside_1_0_is_idempotent():
    from requirements.importer import commit_import
    from requirements import services as rs

    old = commit_import(tutorial.tutorial_data(label="1.0"))
    rs.submit_for_review(old)
    rs.publish_version(old)
    call_command("seed_tutorial")
    call_command("seed_tutorial")
    labels = sorted(AwardVersion.objects.filter(award__slug=tutorial.AWARD_SLUG).values_list("version_label", flat=True))
    assert labels == ["1.0", "1.1"]
    assert "checklist" in RequirementNode.objects.get(award_version=version(), display_number="5").text


def test_ensure_tutorial_plan(user):
    assert services.ensure_tutorial_plan(user) is None  # not seeded: no-op
    call_command("seed_tutorial")
    plan = services.ensure_tutorial_plan(user)
    assert plan.status == LearningPlan.Status.ACTIVE
    assert services.ensure_tutorial_plan(user) is None
    assert LearningPlan.objects.filter(user=user).count() == 1
    services.change_plan_status(plan, LearningPlan.Status.ABANDONED)
    services.change_plan_status(plan, LearningPlan.Status.ARCHIVED)
    assert services.ensure_tutorial_plan(user) is None
    assert LearningPlan.objects.filter(user=user).count() == 1
    other = get_user_model().objects.create_user("other", password="x")
    assert services.ensure_tutorial_plan(other) is not None


def test_my_learning_creates_plan_and_shows_count(client, user):
    call_command("seed_tutorial")
    client.force_login(user)
    html = client.get("/learning/").content.decode()
    assert "How to use Merit Badge" in html and "0 of 10 done" in html
    client.get("/learning/")
    assert LearningPlan.objects.filter(user=user).count() == 1


def test_checklist_mark_done_undo_and_refusal(client, user):
    from django.urls import reverse
    from requirements.models import RequirementActionTag

    call_command("seed_tutorial")
    plan = services.ensure_tutorial_plan(user)
    client.force_login(user)
    html = client.get(reverse("plan_detail", args=[plan.pk])).content.decode()
    assert "Checklist" in html and "Mark done" in html
    p1 = plan.progress.get(requirement_node__display_number="1")
    r = client.post(reverse("progress_check", args=[p1.pk]), {"do": "done", "next": "plan"})
    assert r.status_code == 302
    p1.refresh_from_db()
    assert p1.status == RS.PERSONALLY_COMPLETED
    html = client.get(reverse("plan_detail", args=[plan.pk])).content.decode()
    assert "Undo" in html
    client.post(reverse("progress_check", args=[p1.pk]), {"do": "undo", "next": "plan"})
    p1.refresh_from_db()
    assert p1.status == RS.IN_PROGRESS
    # Rules still apply: a demonstrate tag needs evidence or a statement.
    p2 = plan.progress.get(requirement_node__display_number="2")
    RequirementActionTag.objects.bulk_create([RequirementActionTag(node=p2.requirement_node, tag="demonstrate")])
    r = client.post(reverse("progress_check", args=[p2.pk]), {"do": "done", "next": "plan"}, follow=True)
    p2.refresh_from_db()
    assert p2.status != RS.PERSONALLY_COMPLETED
    body = r.content.decode()
    assert "Reading a resource or an AI session does not count" in body
    assert reverse("progress_detail", args=[p2.pk]) in body
    # Requirement page has the same control.
    assert "Mark done" in client.get(reverse("progress_detail", args=[p1.pk])).content.decode()


def test_learner_pages_hide_tags_and_unofficial_badge_but_editor_keeps_tags(client, user):
    from django.urls import reverse

    call_command("seed_tutorial")
    plan = services.ensure_tutorial_plan(user)
    client.force_login(user)
    p = plan.progress.get(requirement_node__display_number="2")
    pages = [
        reverse("version_detail", args=[version().pk]),
        reverse("plan_detail", args=[plan.pk]),
        reverse("progress_detail", args=[p.pk]),
    ]
    for url in pages:
        html = client.get(url).content.decode()
        assert "Not official text" not in html, url
        assert "unreviewed tag" not in html, url
        assert "Action tag" not in html, url
    html = client.get(pages[2]).content.decode()
    assert 'badge badge-outline">Plan<' not in html
    # Authoring view keeps the tags, labelled.
    from requirements.importer import commit_import

    draft = commit_import(tutorial.tutorial_data(label="9.9"))
    user.is_superuser = True
    user.is_staff = True
    user.save()
    html = client.get(reverse("version_edit", args=[draft.pk])).content.decode()
    assert "Action tag" in html
