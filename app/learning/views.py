"""Learner screens. Every query is scoped to the signed-in user (404 for others)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from programs import services as program_services
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from evidence import services as evidence_services
from evidence.models import EvidenceRecord
from programs.models import AwardVersion
from requirements import services as req_services

from . import guidance, presenters, selectors, services
from .constants import EVIDENCE_TYPES_BY_TAG, NEVER_COUNTS
from .forms import NotesForm, PlanStartForm, PriorKnowledgeForm, StatusForm
from .models import LearningPlan, RequirementProgress

PS = LearningPlan.Status
RS = RequirementProgress.Status

# Plan actions the learner can take from the overview. Completion has its own page.
PLAN_ACTIONS = {
    "pause": (PS.PAUSED, "Plan paused."),
    "resume": (PS.ACTIVE, "Plan resumed."),
    "abandon": (PS.ABANDONED, "Plan abandoned. Your notes and evidence are kept."),
    "archive": (PS.ARCHIVED, "Plan archived."),
}


@login_required
def my_learning(request):
    services.ensure_tutorial_plan(request.user)
    plans = list(selectors.plans_for(request.user).select_related("award_version__award__program"))
    for p in plans:
        summary = services.plan_summary(p)
        p.done_count, p.total_count = summary.requirements_complete, summary.requirements_total
    groups = [
        ("Active", [p for p in plans if p.status in (PS.ACTIVE, PS.PLANNED)]),
        ("Paused", [p for p in plans if p.status == PS.PAUSED]),
        ("Personally completed", [p for p in plans if p.status == PS.PERSONALLY_COMPLETED]),
        ("Abandoned", [p for p in plans if p.status == PS.ABANDONED]),
        ("Archived", [p for p in plans if p.status == PS.ARCHIVED]),
    ]
    return render(
        request, "learning/my_learning.html",
        {"groups": [(name, items) for name, items in groups if items], "has_plans": bool(plans)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def plan_start(request, pk):
    version = get_object_or_404(
        AwardVersion.objects.select_related("award", "award__program"), pk=pk
    )
    program_services.require_view(request.user, version.award.program)
    if version.status != AwardVersion.Status.PUBLISHED:
        messages.error(request, "You can only start a plan from a published version.")
        return redirect("version_detail", pk=version.pk)
    form = PlanStartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            plan = services.create_plan(
                request.user, version,
                title_override=form.cleaned_data["title_override"],
                target_date=form.cleaned_data["target_date"],
                notes=form.cleaned_data["notes"],
            )
            services.start_plan(plan)
        except services.LearningError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Plan started. Your progress is saved as you go.")
            return redirect("plan_detail", pk=plan.pk)
    nodes = req_services.get_tree(version)
    existing = selectors.plans_for(request.user).filter(
        award_version=version, status__in=[PS.PLANNED, PS.ACTIVE, PS.PAUSED]
    )
    return render(
        request, "learning/plan_start.html",
        {
            "version": version, "award": version.award, "tree": nodes, "form": form,
            "existing": existing,
            "requirement_count": sum(1 for _ in req_services.iter_tree(version)),
        },
    )


def _condition_rows(plan):
    answers = plan.condition_answers or {}
    rows = []
    for key, values in services.condition_options(plan.award_version).items():
        rows.append({
            "key": key,
            "options": [{"index": i, "label": str(v)} for i, v in enumerate(values)],
            "answered": key in answers,
            "answer": answers.get(key),
        })
    return rows


def _checklist(tree):
    """Flat list of leaf rows that take a status, in reading order."""
    out = []
    for r in tree:
        if r["leaf"] and r["progress"] and r["key"] not in ("note", "not_applicable"):
            out.append(r)
        out.extend(_checklist(r["children"]))
    return out


def _blocked_progress(request, plan):
    """The requirement whose Mark done was refused, so the page can link to it."""
    raw = request.GET.get("blocked", "")
    if not raw.isdigit():
        return None
    return RequirementProgress.objects.filter(pk=int(raw), learning_plan=plan).select_related(
        "requirement_node"
    ).first()


@login_required
def plan_detail(request, pk):
    plan = selectors.get_plan_for(request.user, pk)
    ctx = presenters.plan_context(plan)
    ctx.update(
        checklist=_checklist(ctx["tree"]),
        blocked_progress=_blocked_progress(request, plan),
        conditions=_condition_rows(plan),
        can_complete=plan.status == PS.ACTIVE and ctx["summary"].satisfied,
        transitions=sorted(
            (a for a, (t, _m) in PLAN_ACTIONS.items()
             if t in LearningPlan.TRANSITIONS.get(plan.status, set())),
        ),
        status_log=plan.status_log.all(),
        achievement=getattr(plan, "achievement", None),
    )
    return render(request, "learning/plan_detail.html", ctx)


@login_required
@require_POST
def plan_action(request, pk, action):
    plan = selectors.get_plan_for(request.user, pk)
    if action not in PLAN_ACTIONS:
        messages.error(request, "Unknown plan action.")
        return redirect("plan_detail", pk=plan.pk)
    target, done = PLAN_ACTIONS[action]
    try:
        services.change_plan_status(plan, target, note=f"Learner chose: {action}")
    except services.LearningError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, done)
    return redirect("plan_detail", pk=plan.pk)


@login_required
@require_POST
def plan_condition(request, pk):
    plan = selectors.get_plan_for(request.user, pk)
    key = request.POST.get("key", "")
    options = services.condition_options(plan.award_version)
    try:
        if key not in options:
            raise services.LearningError(f"This plan has no condition named {key!r}.")
        choice = request.POST.get("answer", "")
        if choice == "":
            services.clear_condition_answer(plan, key)
            messages.success(request, f"Answer for {key} cleared.")
        elif choice == "none":
            # A value no condition can match, so the branch is recorded as not applying.
            services.set_condition_answer(plan, key, "(none of the listed values)")
            messages.success(request, f"Answer for {key} saved.")
        else:
            try:
                value = options[key][int(choice)]
            except (ValueError, IndexError):
                raise services.LearningError("Choose one of the listed answers.")
            services.set_condition_answer(plan, key, value)
            messages.success(request, f"Answer for {key} saved.")
    except services.LearningError as exc:
        messages.error(request, str(exc))
    return redirect("plan_detail", pk=plan.pk)


@login_required
@require_http_methods(["GET", "POST"])
def plan_complete(request, pk):
    plan = selectors.get_plan_for(request.user, pk)
    ctx = presenters.plan_context(plan)
    if request.method == "POST":
        try:
            services.complete_plan(plan)
        except services.LearningError as exc:
            messages.error(request, str(exc))
            return redirect("plan_detail", pk=plan.pk)
        messages.success(request, "Personal completion recorded. Your achievement record is ready.")
        return redirect("achievement_list")
    ctx["can_complete"] = plan.status == PS.ACTIVE and ctx["summary"].satisfied
    return render(request, "learning/plan_complete.html", ctx)


# Requirement detail -------------------------------------------------------------

def _allowed_statuses(progress, state):
    """Statuses the learner may pick next. Not applicable only if a rule says so."""
    if not services._is_leaf(progress.requirement_node):
        return []
    allowed = services.PROGRESS_TRANSITIONS.get(progress.status, set())
    return [
        s for s in RS.values
        if s in allowed and (s != RS.NOT_APPLICABLE or state == presenters.completion.NOT_APPLICABLE)
    ]


@login_required
def progress_detail(request, pk):
    progress = selectors.get_progress_for(request.user, pk)
    plan, node = progress.learning_plan, progress.requirement_node
    result = services.evaluate_plan(plan)
    res = result.nodes.get(node.pk)
    tags = list(node.action_tags.values_list("tag", flat=True))
    leaf = services._is_leaf(node)
    counting = set()
    for t in tags:
        counting |= set(EVIDENCE_TYPES_BY_TAG.get(t, ()))
    counting -= set(NEVER_COUNTS)
    labels = dict(EvidenceRecord.EvidenceType.choices)
    progress_by_node = {
        p.requirement_node_id: p
        for p in RequirementProgress.objects.filter(
            learning_plan=plan, requirement_node__in=list(node.children.all()) + [node.parent_id]
        )
    }
    children = []
    for c in node.children.all():
        c_res = result.nodes.get(c.pk)
        children.append({
            "node": c,
            "progress": progress_by_node.get(c.pk),
            "leaf": services._is_leaf(c),
            "state_label": presenters.STATE_LABELS.get(c_res.state, "") if c_res else "",
        })
    parent_progress = progress_by_node.get(node.parent_id)
    allowed = _allowed_statuses(progress, res.state if res else '')
    return render(request, "learning/progress_detail.html", {
        "progress": progress, "plan": plan, "node": node, "leaf": leaf,
        "version": plan.award_version,
        "state_label": presenters.STATE_LABELS.get(res.state, "") if res else "",
        "blocked": node.pk in result.blocked,
        "outstanding": [o.message for o in (res.outstanding if res else [])],
        "children": children,
        "parent_progress_id": parent_progress.pk if parent_progress else None,
        "guidance": guidance.guidance_for(tags),
        "can_check": leaf and plan.status == PS.ACTIVE
        and progress.status not in (RS.NOT_APPLICABLE,),
        "counting_types": sorted(labels[t] for t in counting),
        "evidence": progress.evidence_records.all(),
        "can_log": "log" in tags or "time_log" in counting,
        "plan_open": plan.status in (PS.PLANNED, PS.ACTIVE, PS.PAUSED),
        "status_form": StatusForm(allowed=allowed) if allowed and plan.status == PS.ACTIVE else None,
        "prior_form": PriorKnowledgeForm(initial={
            "prior_knowledge_claim": progress.prior_knowledge_claim,
            "prior_work_notes": progress.prior_work_notes,
        }),
        "notes_form": NotesForm(initial={"learner_notes": progress.learner_notes}),
        "evidence_problem": services.evidence_problem(progress) if leaf else None,
        "has_interpretation": False,
    })


@login_required
@require_POST
def progress_status(request, pk):
    progress = selectors.get_progress_for(request.user, pk)
    form = StatusForm(request.POST, allowed=RS.values)
    if form.is_valid():
        try:
            services.set_progress_status(progress, form.cleaned_data["status"])
        except services.LearningError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Status saved.")
    else:
        messages.error(request, "Choose a status from the list.")
    return redirect("progress_detail", pk=progress.pk)


@login_required
@require_POST
def progress_check(request, pk):
    """One-click Mark done or Undo. Uses the same rules as the status form."""
    progress = selectors.get_progress_for(request.user, pk)
    plan = progress.learning_plan
    done = request.POST.get("do") != "undo"
    target = RS.PERSONALLY_COMPLETED if done else RS.IN_PROGRESS
    back = request.POST.get("next") == "requirement"
    refused = False
    try:
        services.set_progress_status(progress, target)
    except services.LearningError as exc:
        messages.error(request, str(exc))
        refused = True
    else:
        messages.success(
            request, "Marked done." if done else "Marked as in progress. Your work is kept."
        )
    if back:
        return redirect("progress_detail", pk=progress.pk)
    url = reverse("plan_detail", args=[plan.pk])
    if refused:
        url += f"?blocked={progress.pk}"
    return redirect(f"{url}#req-{progress.pk}")


@login_required
@require_POST
def progress_prior(request, pk):
    progress = selectors.get_progress_for(request.user, pk)
    form = PriorKnowledgeForm(request.POST)
    if form.is_valid():
        try:
            services.record_prior_knowledge(
                progress,
                claim=form.cleaned_data["prior_knowledge_claim"],
                notes=form.cleaned_data["prior_work_notes"],
            )
        except services.LearningError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Saved as a claim and a note. This did not complete the requirement.",
            )
    return redirect("progress_detail", pk=progress.pk)


@login_required
@require_POST
def progress_notes(request, pk):
    progress = selectors.get_progress_for(request.user, pk)
    form = NotesForm(request.POST)
    if form.is_valid():
        services.save_learner_notes(progress, form.cleaned_data["learner_notes"])
        messages.success(request, "Notes saved.")
    return redirect("progress_detail", pk=progress.pk)


@login_required
@require_POST
def progress_attest(request, pk):
    progress = selectors.get_progress_for(request.user, pk)
    try:
        services.record_attestation(progress, attested=request.POST.get("attested") == "1")
    except services.LearningError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Saved. This is your own statement. It does not complete the requirement by itself.",
        )
    return redirect("progress_detail", pk=progress.pk)
