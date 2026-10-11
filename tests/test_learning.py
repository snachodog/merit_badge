"""Plans, progress, statuses, evidence rules and owner scoping."""
import pytest
from django.contrib.auth import get_user_model
from django.http import Http404

from evidence.models import EvidenceRecord
from evidence import services as ev
from learning import selectors, services
from learning.models import LearningPlan, PlanStatusLog, RequirementProgress
from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements import services as req
from requirements.models import RequirementActionTag, RequirementNode

pytestmark = pytest.mark.django_db
RS = RequirementProgress.Status
PS = LearningPlan.Status


@pytest.fixture
def user():
    return get_user_model().objects.create_user("owner", password="x")


@pytest.fixture
def other():
    return get_user_model().objects.create_user("other", password="x")


@pytest.fixture
def award():
    owner = ProgramOwner.objects.create(name="Me", slug="me", owner_type="individual")
    program = Program.objects.create(owner=owner, name="Custom", slug="custom", is_custom=True)
    return Award.objects.create(program=program, name="Bread", slug="bread")


def add(version, num, parent=None, order=0, logic="single", count=None, cond=None, tags=()):
    node = RequirementNode.objects.create(
        award_version=version, parent=parent, sort_order=order, display_number=num,
        text=f"Text {num}", completion_logic=logic, completion_count=count,
        condition_expression=cond,
    )
    for t in tags:
        RequirementActionTag.objects.create(node=node, tag=t)
    return node


def publish(version):
    req.submit_for_review(version)
    return req.publish_version(version)


@pytest.fixture
def simple(award):
    """1 (read) and 2 (interview), both single."""
    v = AwardVersion.objects.create(award=award, version_label="1")
    n1 = add(v, "1", order=0, tags=["read"])
    n2 = add(v, "2", order=1, tags=["interview"])
    publish(v)
    return v, n1, n2


def prog(plan, node):
    return RequirementProgress.objects.get(learning_plan=plan, requirement_node=node)


def active_plan(user, version):
    plan = services.create_plan(user, version)
    return services.start_plan(plan)


# Plan creation, pinning ------------------------------------------------------------

def test_create_plan_makes_progress_rows_for_all_nodes(user, award):
    v = AwardVersion.objects.create(award=award, version_label="1")
    g = add(v, "1", logic="all")
    add(v, "1a", g, 0)
    add(v, "1b", g, 1)
    publish(v)
    plan = services.create_plan(user, v)
    assert plan.status == PS.PLANNED
    assert plan.progress.count() == 3
    assert set(plan.progress.values_list("status", flat=True)) == {RS.NOT_STARTED}


@pytest.mark.parametrize("status", ["draft", "review", "archived"])
def test_unpublished_version_rejected(user, award, status):
    v = AwardVersion.objects.create(award=award, version_label="1")
    add(v, "1")
    if status == "review":
        req.submit_for_review(v)
    if status == "archived":
        publish(v)
        req.archive_version(v)
    with pytest.raises(services.LearningError):
        services.create_plan(user, v)
    assert LearningPlan.objects.count() == 0


def test_model_also_refuses_unpublished_version(user, award):
    from django.core.exceptions import ValidationError
    v = AwardVersion.objects.create(award=award, version_label="1")
    with pytest.raises(ValidationError):
        LearningPlan.objects.create(user=user, award_version=v)


def test_plan_stays_pinned_when_new_revision_is_published(user, simple):
    v, _, _ = simple
    plan = services.create_plan(user, v)
    rev = req.create_revision(v)
    publish(rev)
    plan.refresh_from_db()
    assert plan.award_version_id == v.pk
    assert plan.progress.count() == 2
    plan.award_version = rev
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        plan.save()


def test_progress_never_changes_definitions(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    services.record_attestation(prog(plan, n1))
    services.set_progress_status(prog(plan, n1), RS.PERSONALLY_COMPLETED)
    v.refresh_from_db()
    assert v.status == AwardVersion.Status.PUBLISHED
    assert not hasattr(n1, "status")


# Plan status log ---------------------------------------------------------------------

def test_plan_transitions_are_logged_and_validated(user, simple):
    v, _, _ = simple
    plan = services.create_plan(user, v)
    services.start_plan(plan)
    services.change_plan_status(plan, PS.PAUSED)
    services.change_plan_status(plan, PS.ACTIVE)
    services.change_plan_status(plan, PS.ABANDONED)
    services.change_plan_status(plan, PS.ARCHIVED)
    log = list(PlanStatusLog.objects.filter(plan=plan).values_list("from_status", "to_status"))
    assert log == [("", "planned"), ("planned", "active"), ("active", "paused"),
                   ("paused", "active"), ("active", "abandoned"), ("abandoned", "archived")]
    with pytest.raises(services.LearningError):
        services.change_plan_status(plan, PS.ACTIVE)
    plan.refresh_from_db()
    assert plan.started_at is not None


def test_invalid_plan_transition(user, simple):
    plan = services.create_plan(user, simple[0])
    with pytest.raises(services.LearningError):
        services.change_plan_status(plan, PS.PAUSED)


def test_cannot_complete_through_generic_transition(user, simple):
    plan = active_plan(user, simple[0])
    with pytest.raises(services.LearningError):
        services.change_plan_status(plan, PS.PERSONALLY_COMPLETED)


# Prior knowledge ------------------------------------------------------------------------

def test_prior_knowledge_never_completes(user, simple):
    v, n1, _ = simple
    plan = active_plan(user, v)
    p = prog(plan, n1)
    services.record_prior_knowledge(p, claim=True, notes="I did this years ago")
    p.refresh_from_db()
    assert p.prior_knowledge_claim and p.prior_work_notes
    assert p.status == RS.NOT_STARTED and p.personally_completed_at is None
    assert not services.plan_summary(plan).satisfied
    assert services.plan_summary(plan).requirements_complete == 0


def test_prior_knowledge_can_be_recorded_before_start(user, simple):
    v, n1, _ = simple
    plan = services.create_plan(user, v)
    services.record_prior_knowledge(prog(plan, n1), claim=True)
    assert prog(plan, n1).status == RS.NOT_STARTED


def test_status_change_needs_active_plan(user, simple):
    v, n1, _ = simple
    plan = services.create_plan(user, v)
    with pytest.raises(services.LearningError):
        services.set_progress_status(prog(plan, n1), RS.IN_PROGRESS)


# Status transitions ---------------------------------------------------------------------

def test_simple_requirement_completes_and_can_reopen(user, simple):
    v, n1, _ = simple
    plan = active_plan(user, v)
    p = services.set_progress_status(prog(plan, n1), RS.IN_PROGRESS)
    p = services.set_progress_status(p, RS.PERSONALLY_COMPLETED)  # read: no evidence needed
    assert p.personally_completed_at is not None
    p = services.set_progress_status(p, RS.NEEDS_MORE_WORK)
    assert p.personally_completed_at is None
    with pytest.raises(services.LearningError):
        services.set_progress_status(p, "bogus")


def test_completed_cannot_jump_to_not_started(user, simple):
    v, n1, _ = simple
    plan = active_plan(user, v)
    p = services.set_progress_status(prog(plan, n1), RS.PERSONALLY_COMPLETED)
    with pytest.raises(services.LearningError):
        services.set_progress_status(p, RS.NOT_STARTED)


def test_group_status_cannot_be_set(user, award):
    v = AwardVersion.objects.create(award=award, version_label="1")
    g = add(v, "1", logic="all")
    add(v, "1a", g)
    publish(v)
    plan = active_plan(user, v)
    with pytest.raises(services.LearningError):
        services.set_progress_status(prog(plan, g), RS.PERSONALLY_COMPLETED)


# Not applicable -------------------------------------------------------------------------

def test_not_applicable_rejected_without_rule(user, simple):
    v, n1, _ = simple
    plan = active_plan(user, v)
    with pytest.raises(services.LearningError):
        services.set_progress_status(prog(plan, n1), RS.NOT_APPLICABLE)
    assert prog(plan, n1).status == RS.NOT_STARTED


@pytest.fixture
def conditional(award):
    v = AwardVersion.objects.create(award=award, version_label="1")
    always = add(v, "1", order=0)
    cond = add(v, "2", order=1, logic="conditional", cond={"key": "has_pet", "equals": "yes"})
    leaf = add(v, "2a", cond, 0)
    publish(v)
    return v, always, cond, leaf


def test_not_applicable_allowed_only_when_condition_says_so(user, conditional):
    v, always, cond, leaf = conditional
    plan = active_plan(user, v)
    with pytest.raises(services.LearningError):  # unanswered
        services.set_progress_status(prog(plan, leaf), RS.NOT_APPLICABLE)
    services.set_condition_answer(plan, "has_pet", "yes")
    with pytest.raises(services.LearningError):  # condition holds, so it applies
        services.set_progress_status(prog(plan, leaf), RS.NOT_APPLICABLE)
    services.set_condition_answer(plan, "has_pet", "no")
    p = services.set_progress_status(prog(plan, leaf), RS.NOT_APPLICABLE)
    assert p.status == RS.NOT_APPLICABLE
    with pytest.raises(services.LearningError):
        services.set_progress_status(prog(plan, always), RS.NOT_APPLICABLE)


def test_unknown_condition_key_rejected(user, conditional):
    plan = active_plan(user, conditional[0])
    with pytest.raises(services.LearningError):
        services.set_condition_answer(plan, "nope", "x")


def test_completing_a_not_applicable_requirement_is_refused(user, conditional):
    v, always, cond, leaf = conditional
    plan = active_plan(user, v)
    services.set_condition_answer(plan, "has_pet", "no")
    with pytest.raises(services.LearningError):
        services.set_progress_status(prog(plan, leaf), RS.PERSONALLY_COMPLETED)


def test_plan_with_conditional_branch_completes(user, conditional):
    v, always, cond, leaf = conditional
    plan = active_plan(user, v)
    assert services.plan_summary(plan).state == "incomplete"
    services.set_progress_status(prog(plan, always), RS.PERSONALLY_COMPLETED)
    assert services.plan_summary(plan).state == "unresolved"
    with pytest.raises(services.LearningError):
        services.complete_plan(plan)
    services.set_condition_answer(plan, "has_pet", "no")
    done = services.complete_plan(plan)
    assert done.status == PS.PERSONALLY_COMPLETED and done.personal_completed_at


# Sequence ---------------------------------------------------------------------------------

def test_sequence_order_enforced(user, award):
    v = AwardVersion.objects.create(award=award, version_label="1")
    g = add(v, "1", logic="sequence")
    a, b = add(v, "1a", g, 0), add(v, "1b", g, 1)
    publish(v)
    plan = active_plan(user, v)
    with pytest.raises(services.LearningError):
        services.set_progress_status(prog(plan, b), RS.PERSONALLY_COMPLETED)
    services.set_progress_status(prog(plan, a), RS.PERSONALLY_COMPLETED)
    services.set_progress_status(prog(plan, b), RS.PERSONALLY_COMPLETED)
    assert services.complete_plan(plan).status == PS.PERSONALLY_COMPLETED


# choose_n through the services ---------------------------------------------------------------

def test_choose_n_via_services(user, award):
    v = AwardVersion.objects.create(award=award, version_label="1")
    g = add(v, "1", logic="choose_n", count=2)
    kids = [add(v, f"1{c}", g, i) for i, c in enumerate("abc")]
    publish(v)
    plan = active_plan(user, v)
    services.set_progress_status(prog(plan, kids[0]), RS.PERSONALLY_COMPLETED)
    with pytest.raises(services.LearningError):
        services.complete_plan(plan)
    services.set_progress_status(prog(plan, kids[2]), RS.PERSONALLY_COMPLETED)
    summary = services.plan_summary(plan)
    assert summary.satisfied and summary.requirements_complete == 2
    services.complete_plan(plan)


def test_plan_complete_needs_learner_action(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    services.set_progress_status(prog(plan, n1), RS.PERSONALLY_COMPLETED)
    services.record_attestation(prog(plan, n2))
    services.set_progress_status(prog(plan, n2), RS.PERSONALLY_COMPLETED)
    plan.refresh_from_db()
    assert services.plan_summary(plan).satisfied
    assert plan.status == PS.ACTIVE and plan.personal_completed_at is None
    services.complete_plan(plan)
    plan.refresh_from_db()
    assert plan.status == PS.PERSONALLY_COMPLETED
    with pytest.raises(services.LearningError):
        services.complete_plan(plan)


# Action-tag evidence rule ---------------------------------------------------------------------

def test_tagged_requirement_needs_evidence_or_attestation(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    p = prog(plan, n2)  # interview
    with pytest.raises(services.LearningError, match="interview"):
        services.set_progress_status(p, RS.PERSONALLY_COMPLETED)


def test_prior_work_notes_do_not_satisfy_evidence_rule(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    p = prog(plan, n2)
    services.record_prior_knowledge(p, claim=True, notes="done long ago")
    with pytest.raises(services.LearningError):
        services.set_progress_status(p, RS.PERSONALLY_COMPLETED)


def test_suitable_evidence_allows_completion(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    p = prog(plan, n2)
    ev.add_text_evidence(user, p, "note", title="Interview with Sam", description="Q and A")
    assert services.set_progress_status(p, RS.PERSONALLY_COMPLETED).status == RS.PERSONALLY_COMPLETED


def test_ai_summary_and_link_evidence_do_not_count(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    p = prog(plan, n2)
    ev.add_text_evidence(user, p, "ai_practice_summary", title="AI chat", description="x")
    ev.add_text_evidence(user, p, "external_link", external_url="https://example.com/read")
    with pytest.raises(services.LearningError):
        services.set_progress_status(p, RS.PERSONALLY_COMPLETED)


def test_unsuitable_type_for_demonstrate(user, award):
    v = AwardVersion.objects.create(award=award, version_label="1")
    n = add(v, "1", tags=["demonstrate"])
    publish(v)
    plan = active_plan(user, v)
    p = prog(plan, n)
    ev.add_text_evidence(user, p, "text_response", description="I describe how I did it")
    with pytest.raises(services.LearningError):  # text alone is not a demonstration
        services.set_progress_status(p, RS.PERSONALLY_COMPLETED)
    ev.add_text_evidence(user, p, "witness_record", description="Sam watched me")
    services.set_progress_status(p, RS.PERSONALLY_COMPLETED)


def test_explicit_attestation_allows_completion(user, simple):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    p = prog(plan, n2)
    services.record_attestation(p)
    assert services.set_progress_status(p, RS.PERSONALLY_COMPLETED).status == RS.PERSONALLY_COMPLETED


# Owner scoping -----------------------------------------------------------------------------------

def test_other_user_gets_404_for_plan_and_progress(user, other, simple):
    v, n1, _ = simple
    plan = services.create_plan(user, v)
    p = prog(plan, n1)
    assert selectors.get_plan_for(user, plan.pk) == plan
    assert selectors.get_progress_for(user, p.pk) == p
    with pytest.raises(Http404):
        selectors.get_plan_for(other, plan.pk)
    with pytest.raises(Http404):
        selectors.get_progress_for(other, p.pk)
    assert not selectors.plans_for(other).exists()
    assert not selectors.progress_for(other).exists()


def test_delete_plan_reports_and_removes_evidence(user, simple, django_capture_on_commit_callbacks):
    v, n1, n2 = simple
    plan = active_plan(user, v)
    ev.add_text_evidence(user, prog(plan, n2), "note", title="n", description="d")
    report = services.delete_plan(plan)
    assert report.records == 1
    assert not LearningPlan.objects.exists() and not EvidenceRecord.objects.exists()
