"""Build what the learner screens show. No writes here."""
from requirements import services as req_services
from requirements.models import RequirementNode

from . import completion, services
from .models import RequirementProgress

RS = RequirementProgress.Status

STATE_LABELS = {
    completion.COMPLETE: "Complete",
    completion.INCOMPLETE: "Not complete",
    completion.UNRESOLVED: "Needs an answer",
    completion.NOT_APPLICABLE: "Does not apply",
}

# Order of the summary counts (PLAN.md 12.4).
COUNT_ORDER = [
    ("personally_completed", "Completed personally"),
    ("in_progress", "In progress"),
    ("awaiting_evidence", "Awaiting evidence"),
    ("ready_for_review", "Ready for review"),
    ("needs_more_work", "Needs more work"),
    ("not_started", "Not yet started"),
    ("not_applicable", "Does not apply"),
]


def _is_leaf_node(node, parent_ids):
    return node.completion_logic == "single" and node.pk not in parent_ids


def plan_context(plan):
    """Summary, status counts, nested tree rows and outstanding items for one plan."""
    version = plan.award_version
    result = services.evaluate_plan(plan)
    progress = {
        p.requirement_node_id: p
        for p in RequirementProgress.objects.filter(learning_plan=plan)
    }
    nodes = {n.pk: n for n in RequirementNode.objects.filter(award_version=version)}
    parent_ids = {n.parent_id for n in nodes.values() if n.parent_id}
    counts = {key: 0 for key, _ in COUNT_ORDER}

    def row(item):
        node = item.node
        res = result.nodes.get(node.pk)
        state = res.state if res else completion.INCOMPLETE
        leaf = _is_leaf_node(node, parent_ids)
        prog = progress.get(node.pk)
        if node.node_type == RequirementNode.NodeType.NOTE:
            label, key = "Note, nothing to complete", "note"
        elif state == completion.NOT_APPLICABLE:
            label, key = STATE_LABELS[state], "not_applicable"
            if leaf:
                counts["not_applicable"] += 1
        elif leaf:
            label, key = prog.get_status_display(), prog.status
            counts[prog.status] += 1
        else:
            label, key = STATE_LABELS.get(state, state), state
        return {
            "node": node,
            "progress": prog,
            "leaf": leaf,
            "state": state,
            "key": key,
            "label": label,
            "blocked": node.pk in result.blocked,
            "children": [row(c) for c in item.children],
        }

    tree = [row(i) for i in req_services.get_tree(version)]
    progress_ids = {nid: p.pk for nid, p in progress.items()}
    outstanding = [
        {
            "message": o.message,
            "progress_id": progress_ids.get(o.key),
            "blocked": o.blocked_by is not None,
        }
        for o in result.outstanding
    ]
    summary = services.plan_summary(plan)
    return {
        "plan": plan,
        "version": version,
        "summary": summary,
        "counts": [(label, counts[key]) for key, label in COUNT_ORDER],
        "tree": tree,
        "outstanding": outstanding,
        "result": result,
    }
