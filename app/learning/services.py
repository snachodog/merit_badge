"""Learning workflow services. Views call these, not the models.

Rules enforced here (PLAN.md sections 4.1, 6.8, 6.9, 7.2):
- A plan starts only from a published version and stays pinned to it.
- Creating a plan creates one progress row per requirement node.
- Only single (leaf) requirements take a status. Groups are derived.
- Prior knowledge and prior work notes never change a status.
- A requirement is completed only by `set_progress_status(..., PERSONALLY_COMPLETED)`,
  and only if sequence order and the evidence rule (see constants.py) allow it.
- `not_applicable_by_explicit_rule` is accepted only when a conditional
  requirement's answered condition makes the branch not apply.
- A plan is personally completed only if the engine says it is satisfied and
  the learner calls `complete_plan`.
"""
from dataclasses import dataclass

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from programs.models import AwardVersion
from requirements import services as req_services
from requirements import tree_rules
from requirements.models import RequirementNode

from . import completion
from .constants import EVIDENCE_TYPES_BY_TAG, NEVER_COUNTS
from .models import LearningPlan, PlanStatusLog, RequirementProgress

PS = LearningPlan.Status
RS = RequirementProgress.Status


class LearningError(ValueError):
    """The action is not allowed. The message is safe to show."""


# Plans ------------------------------------------------------------------------

def _log(plan, from_status, to_status, note=""):
    PlanStatusLog.objects.create(
        plan=plan, from_status=from_status or "", to_status=to_status, note=note[:300]
    )


@transaction.atomic
def create_plan(user, version, *, title_override="", target_date=None, notes=""):
    """Make a plan in `planned` status with progress rows for every node."""
    if version.status != AwardVersion.Status.PUBLISHED:
        raise LearningError("You can only start a plan from a published version.")
    plan = LearningPlan.objects.create(
        user=user,
        award_version=version,
        title_override=title_override,
        target_date=target_date,
        notes=notes,
    )
    nodes = RequirementNode.objects.filter(award_version=version).values_list("pk", flat=True)
    RequirementProgress.objects.bulk_create(
        RequirementProgress(learning_plan=plan, requirement_node_id=pk) for pk in nodes
    )
    _log(plan, "", PS.PLANNED, "Plan created")
    return plan


@transaction.atomic
def change_plan_status(plan, target, note=""):
    """Move a plan to a new status if the table allows it. Logs every change."""
    plan = LearningPlan.objects.select_for_update().get(pk=plan.pk)
    if target == PS.PERSONALLY_COMPLETED:
        raise LearningError("Use complete_plan to record personal completion.")
    if target not in LearningPlan.TRANSITIONS.get(plan.status, set()):
        raise LearningError(f"A {plan.status} plan cannot become {target}.")
    old = plan.status
    plan.status = target
    if target == PS.ACTIVE and plan.started_at is None:
        plan.started_at = timezone.now()
    plan.save()
    _log(plan, old, target, note)
    return plan


def start_plan(plan):
    return change_plan_status(plan, PS.ACTIVE, "Started")


@transaction.atomic
def complete_plan(plan, note=""):
    """The learner's personal-completion action. The engine must say satisfied first."""
    plan = LearningPlan.objects.select_for_update().get(pk=plan.pk)
    if plan.status != PS.ACTIVE:
        raise LearningError("Only an active plan can be personally completed.")
    result = evaluate_plan(plan)
    if not result.satisfied:
        raise LearningError(
            "The requirement logic is not satisfied yet. "
            f"{len(result.outstanding)} item(s) are still outstanding."
        )
    now = timezone.now()
    plan.status = PS.PERSONALLY_COMPLETED
    plan.personal_completed_at = now
    plan.save()
    _log(plan, PS.ACTIVE, PS.PERSONALLY_COMPLETED, note or "Personal completion recorded")
    # The only place an achievement record is made (PLAN.md 6.13).
    from achievements import services as achievement_services

    achievement_services.record_completion(plan)
    return plan


@transaction.atomic
def delete_plan(plan):
    """Delete a plan, its progress and its evidence. Returns the evidence report."""
    from evidence import services as evidence_services

    report = evidence_services.deletion_report_for_plan(plan)
    try:
        plan.delete()  # files are removed after commit by the evidence signal
    except ProtectedError as exc:
        raise LearningError(
            "This plan has an achievement record, so it cannot be deleted."
        ) from exc
    return report


# Engine glue -------------------------------------------------------------------

def evaluate_plan(plan):
    """Run the completion engine on the plan's pinned version and current progress."""
    specs = req_services.node_specs(plan.award_version)
    statuses = dict(
        RequirementProgress.objects.filter(learning_plan=plan).values_list(
            "requirement_node_id", "status"
        )
    )
    notes = RequirementNode.objects.filter(
        award_version=plan.award_version, node_type=RequirementNode.NodeType.NOTE
    ).values_list("pk", flat=True)
    return completion.evaluate(
        specs, statuses, plan.condition_answers or {}, ignored_keys=set(notes)
    )


@dataclass
class PlanSummary:
    state: str
    satisfied: bool
    requirements_complete: int
    requirements_total: int
    unresolved: int
    outstanding: list


def plan_summary(plan):
    """Counts and outstanding items, all derived from the engine."""
    result = evaluate_plan(plan)
    return PlanSummary(
        state=result.state,
        satisfied=result.satisfied,
        requirements_complete=result.leaves_complete,
        requirements_total=result.leaves_total,
        unresolved=result.leaves_unresolved,
        outstanding=result.outstanding,
    )


def conditional_keys(version):
    return {
        n.condition_expression["key"]
        for n in RequirementNode.objects.filter(
            award_version=version, completion_logic=tree_rules.CONDITIONAL
        )
        if isinstance(n.condition_expression, dict) and "key" in n.condition_expression
    }


def clear_condition_answer(plan, key):
    """Remove an answer. The condition becomes unresolved again."""
    answers = dict(plan.condition_answers or {})
    answers.pop(key, None)
    plan.condition_answers = answers
    plan.save(update_fields=["condition_answers", "updated_at"])
    return plan


def condition_options(version):
    """{key: [allowed values]} from the version's conditional nodes, in a stable order."""
    options = {}
    for n in RequirementNode.objects.filter(
        award_version=version, completion_logic=tree_rules.CONDITIONAL
    ).order_by("pk"):
        expr = n.condition_expression
        if isinstance(expr, dict) and "key" in expr and "equals" in expr:
            values = options.setdefault(expr["key"], [])
            if expr["equals"] not in values:
                values.append(expr["equals"])
    return options


def set_condition_answer(plan, key, value):
    """Record the learner's answer to a documented condition of this version."""
    if key not in conditional_keys(plan.award_version):
        raise LearningError(f"This plan has no condition named {key!r}.")
    if not isinstance(value, (str, int, bool)):
        raise LearningError("An answer must be text, a number, or true/false.")
    plan.condition_answers = {**(plan.condition_answers or {}), key: value}
    plan.save(update_fields=["condition_answers", "updated_at"])
    return plan


# Requirement progress ------------------------------------------------------------

# Allowed status changes for a single requirement. Anything not listed is refused.
# Completion and not-applicable have extra checks in set_progress_status.
_ANY_WORKING = {RS.IN_PROGRESS, RS.AWAITING_EVIDENCE, RS.READY_FOR_REVIEW, RS.NEEDS_MORE_WORK}
PROGRESS_TRANSITIONS = {
    RS.NOT_STARTED: _ANY_WORKING | {RS.PERSONALLY_COMPLETED, RS.NOT_APPLICABLE},
    RS.IN_PROGRESS: _ANY_WORKING | {RS.NOT_STARTED, RS.PERSONALLY_COMPLETED, RS.NOT_APPLICABLE},
    RS.AWAITING_EVIDENCE: _ANY_WORKING | {RS.PERSONALLY_COMPLETED, RS.NOT_APPLICABLE},
    RS.READY_FOR_REVIEW: _ANY_WORKING | {RS.PERSONALLY_COMPLETED, RS.NOT_APPLICABLE},
    RS.NEEDS_MORE_WORK: _ANY_WORKING | {RS.PERSONALLY_COMPLETED, RS.NOT_APPLICABLE},
    RS.PERSONALLY_COMPLETED: {RS.NEEDS_MORE_WORK, RS.IN_PROGRESS},
    RS.NOT_APPLICABLE: {RS.NOT_STARTED, RS.IN_PROGRESS},
}


def evidence_problem(progress):
    """Return a message if action-tag rules block completion, else None."""
    tags = set(progress.requirement_node.action_tags.values_list("tag", flat=True))
    needed_tags = sorted(tags & set(EVIDENCE_TYPES_BY_TAG))
    if not needed_tags:
        return None
    if progress.self_attested_at is not None:
        return None
    suitable = set()
    for tag in needed_tags:
        suitable |= set(EVIDENCE_TYPES_BY_TAG[tag])
    suitable -= set(NEVER_COUNTS)
    if progress.evidence_records.filter(evidence_type__in=suitable).exists():
        return None
    return (
        f"This requirement is tagged {', '.join(needed_tags)}. Add evidence of one of these "
        f"types ({', '.join(sorted(suitable))}) or record that you did it yourself. "
        "Reading a resource or an AI session does not count."
    )


def _is_leaf(node):
    return node.completion_logic == tree_rules.SINGLE and not node.children.exists()


@transaction.atomic
def set_progress_status(progress, target):
    """Change one requirement's status, applying every rule."""
    progress = RequirementProgress.objects.select_for_update().select_related(
        "learning_plan", "requirement_node"
    ).get(pk=progress.pk)
    plan, node = progress.learning_plan, progress.requirement_node
    if plan.status != PS.ACTIVE:
        raise LearningError("Start the plan before you change a requirement's status.")
    if target not in RS.values:
        raise LearningError(f"Unknown status: {target!r}.")
    if not _is_leaf(node):
        raise LearningError(
            "This is a group. Its status comes from the requirements inside it."
        )
    if target == progress.status:
        return progress
    if target not in PROGRESS_TRANSITIONS.get(progress.status, set()):
        raise LearningError(f"A requirement that is {progress.status} cannot become {target}.")

    if target in (RS.PERSONALLY_COMPLETED, RS.NOT_APPLICABLE):
        result = evaluate_plan(plan)
        state = result.nodes[node.pk].state
        if target == RS.NOT_APPLICABLE:
            if state != completion.NOT_APPLICABLE:
                raise LearningError(
                    "This requirement is only not applicable when a conditional rule in the "
                    "requirements says so. It cannot be skipped."
                )
        else:
            if state == completion.NOT_APPLICABLE:
                raise LearningError("This requirement does not apply to this plan.")
            if node.pk in result.blocked:
                raise LearningError(
                    "Requirements in this group must be completed in order. "
                    "Finish the earlier ones first."
                )
            problem = evidence_problem(progress)
            if problem:
                raise LearningError(problem)

    now = timezone.now()
    progress.status = target
    progress.personally_completed_at = now if target == RS.PERSONALLY_COMPLETED else None
    progress.save()
    return progress


def record_prior_knowledge(progress, *, claim, notes=""):
    """Store the learner's claim and notes. Never changes the status."""
    if progress.learning_plan.status in (PS.ABANDONED, PS.ARCHIVED, PS.PERSONALLY_COMPLETED):
        raise LearningError("This plan is closed.")
    progress.prior_knowledge_claim = bool(claim)
    progress.prior_work_notes = notes
    progress.save(update_fields=["prior_knowledge_claim", "prior_work_notes", "updated_at"])
    return progress


def record_attestation(progress, *, attested=True):
    """The learner states, explicitly, that they did the requested activity."""
    if progress.learning_plan.status != PS.ACTIVE:
        raise LearningError("Start the plan before you record an attestation.")
    progress.self_attested_at = timezone.now() if attested else None
    progress.save(update_fields=["self_attested_at", "updated_at"])
    return progress


def save_learner_notes(progress, notes):
    progress.learner_notes = notes
    progress.save(update_fields=["learner_notes", "updated_at"])
    return progress


# Tutorial ------------------------------------------------------------------------

def ensure_tutorial_plan(user):
    """Give the user a started tutorial plan once. Returns the plan, or None.

    Does nothing if the tutorial is not seeded, or if the user ever had a plan for
    it (including one they archived or abandoned). Uses the newest published version.
    """
    from programs import tutorial

    awards = AwardVersion.objects.filter(
        award__program__owner__slug=tutorial.OWNER_SLUG,
        award__program__slug=tutorial.PROGRAM_SLUG,
        award__slug=tutorial.AWARD_SLUG,
    )
    if LearningPlan.objects.filter(user=user, award_version__in=awards).exists():
        return None
    version = (
        awards.filter(status=AwardVersion.Status.PUBLISHED)
        .order_by("-published_at", "-pk").first()
    )
    if version is None:
        return None
    with transaction.atomic():
        plan = start_plan(create_plan(user, version))
    return plan
