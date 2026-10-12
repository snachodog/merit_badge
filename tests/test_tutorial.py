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
    assert f"/versions/{version().pk}/" in client.get("/").content.decode()
