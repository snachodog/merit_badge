"""Pure completion engine. No Django, no database, nothing about any one organization.

Callers pass the requirement tree as `tree_rules.NodeSpec` objects, the
status of each single (leaf) requirement, and the learner's answers to
conditions. The engine says, for every node, whether it is complete,
incomplete, unresolved or not applicable (PLAN.md section 7).

Rules
- single: complete only when its status is `personally_completed`.
  No other status counts. Prior knowledge is not a status here, so it
  cannot complete anything.
- all: complete when every applicable child is complete.
- any: complete when at least one applicable child is complete.
- choose_n: complete when `completion_count` applicable children are complete.
  If fewer children are applicable than the count, the count drops to the
  number of applicable children. If none are applicable, the node is not applicable.
- sequence: like all, but a child is blocked until every earlier applicable
  child is complete. `blocked` lists those nodes.
- conditional: reads `condition_expression` {"key", "equals"} against the
  learner's answers. No answer: unresolved. Answer equals: the children
  apply as in "all". Answer differs: the whole branch is not applicable.
- A node with no applicable children is not applicable.
- "Unresolved" means an unanswered condition decides the outcome. It is
  never complete.

The plan is satisfied only when the top-level result is `complete`.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Mapping, Optional

from requirements import tree_rules

COMPLETE = "complete"
INCOMPLETE = "incomplete"
UNRESOLVED = "unresolved"
NOT_APPLICABLE = "not_applicable"

# The only leaf status that counts. Kept as plain text so this module needs no Django.
LEAF_COMPLETE_STATUS = "personally_completed"


@dataclass(frozen=True)
class Outstanding:
    key: Hashable
    message: str
    blocked_by: Optional[Hashable] = None


@dataclass
class NodeResult:
    state: str
    outstanding: List[Outstanding] = field(default_factory=list)


@dataclass
class PlanResult:
    state: str
    nodes: Dict[Hashable, NodeResult]
    outstanding: List[Outstanding]
    blocked: Dict[Hashable, Hashable]  # node key -> key of the node it waits for
    # Counts of single requirements, alternatives included. Derived, never edited by a user.
    leaves_total: int  # applicable single requirements
    leaves_complete: int
    leaves_unresolved: int

    @property
    def satisfied(self):
        return self.state == COMPLETE


def condition_holds(expression, answers):
    """True, False, or None if the learner has not answered. Types must match."""
    key = expression["key"]
    if key not in answers:
        return None
    given, wanted = answers[key], expression["equals"]
    return type(given) is type(wanted) and given == wanted


def evaluate(
    nodes,
    leaf_statuses: Mapping[Hashable, str],
    condition_answers: Optional[Mapping[str, Any]] = None,
    ignored_keys=(),
) -> PlanResult:
    """Evaluate a whole tree.

    nodes: iterable of NodeSpec. leaf_statuses: node key -> status text.
    ignored_keys: nodes that need no completion (for example notes).
    """
    nodes = list(nodes)
    answers = condition_answers or {}
    ignored = set(ignored_keys)
    by_key = {n.key: n for n in nodes}
    kids: Dict[Optional[Hashable], list] = {}
    for spec, _depth in tree_rules.walk(nodes):
        parent = spec.parent_key if spec.parent_key in by_key else None
        kids.setdefault(parent, []).append(spec)

    results: Dict[Hashable, NodeResult] = {}
    blocked: Dict[Hashable, Hashable] = {}
    counts = {"total": 0, "complete": 0, "unresolved": 0}

    def mark_na(spec):
        results[spec.key] = NodeResult(NOT_APPLICABLE)
        for child in kids.get(spec.key, []):
            mark_na(child)

    def block_subtree(spec, blocker):
        blocked[spec.key] = blocker
        for child in kids.get(spec.key, []):
            block_subtree(child, blocker)

    def label(spec):
        return spec.display_number or f"requirement {spec.key}"

    def combine_all(spec, children, sequential=False):
        applicable = []
        prior_incomplete = None
        for child in children:
            res = visit(child)
            if res.state == NOT_APPLICABLE:
                continue
            applicable.append((child, res))
        if not applicable:
            return NodeResult(NOT_APPLICABLE)
        outstanding: List[Outstanding] = []
        any_incomplete = any_unresolved = False
        for child, res in applicable:
            if res.state == COMPLETE:
                continue
            if res.state == INCOMPLETE:
                any_incomplete = True
            else:
                any_unresolved = True
            if sequential and prior_incomplete is not None:
                block_subtree(child, prior_incomplete)
                outstanding.extend(
                    Outstanding(o.key, o.message, blocked_by=prior_incomplete)
                    for o in res.outstanding
                )
            else:
                outstanding.extend(res.outstanding)
            if sequential and prior_incomplete is None:
                prior_incomplete = child.key
        if any_incomplete:
            return NodeResult(INCOMPLETE, outstanding)
        if any_unresolved:
            return NodeResult(UNRESOLVED, outstanding)
        return NodeResult(COMPLETE)

    def combine_count(spec, children, need):
        applicable = []
        for child in children:
            res = visit(child)
            if res.state != NOT_APPLICABLE:
                applicable.append((child, res))
        if not applicable:
            return NodeResult(NOT_APPLICABLE)
        need = min(need, len(applicable))
        done = sum(1 for _, r in applicable if r.state == COMPLETE)
        unresolved = sum(1 for _, r in applicable if r.state == UNRESOLVED)
        if done >= need:
            return NodeResult(COMPLETE)
        remaining = need - done
        total = len(applicable)
        if need == 1 and total == 1:
            message = f"Complete {label(applicable[0][0])}."
        elif need == 1:
            message = f"Complete at least 1 of the {total} options under {label(spec)}."
        else:
            message = (
                f"Complete {remaining} more of the {total} options under {label(spec)} "
                f"({done} of {need} done)."
            )
        state = UNRESOLVED if done + unresolved >= need and unresolved else INCOMPLETE
        return NodeResult(state, [Outstanding(spec.key, message)])

    def visit(spec) -> NodeResult:
        if spec.key in results:
            return results[spec.key]
        children = kids.get(spec.key, [])
        logic = spec.completion_logic
        if spec.key in ignored:
            mark_na(spec)
            return results[spec.key]
        if logic == tree_rules.SINGLE or (not children and logic != tree_rules.CONDITIONAL):
            counts["total"] += 1
            status = leaf_statuses.get(spec.key, "not_started")
            if status == LEAF_COMPLETE_STATUS:
                counts["complete"] += 1
                res = NodeResult(COMPLETE)
            else:
                res = NodeResult(
                    INCOMPLETE,
                    [Outstanding(spec.key, f"{label(spec)} is not yet personally completed.")],
                )
        elif logic == tree_rules.CONDITIONAL:
            expr = spec.condition_expression
            valid = isinstance(expr, dict) and "key" in expr and "equals" in expr
            held = condition_holds(expr, answers) if valid else None
            if held is None:
                counts["unresolved"] += 1
                key = expr.get("key", "?") if isinstance(expr, dict) else "?"
                res = NodeResult(
                    UNRESOLVED,
                    [Outstanding(spec.key, f"Answer the condition {key!r} for {label(spec)}.")],
                )
            elif held is False:
                mark_na(spec)
                return results[spec.key]
            else:
                res = combine_all(spec, children)
        elif logic == tree_rules.ALL:
            res = combine_all(spec, children)
        elif logic == tree_rules.SEQUENCE:
            res = combine_all(spec, children, sequential=True)
        elif logic == tree_rules.ANY:
            res = combine_count(spec, children, 1)
        elif logic == tree_rules.CHOOSE_N:
            res = combine_count(spec, children, spec.completion_count or 1)
        else:  # unknown logic: never guess completion
            res = NodeResult(INCOMPLETE, [Outstanding(spec.key, f"{label(spec)} has unknown logic.")])
        results[spec.key] = res
        return res

    roots = kids.get(None, [])
    for root in roots:
        visit(root)
    # Visit anything unreachable (bad data) so every key has a result.
    for n in nodes:
        if n.key not in results:
            visit(n)

    top = NodeResult(NOT_APPLICABLE)
    if roots:
        top = combine_all(None, roots)
        # Roots that are all not applicable leave nothing to complete: cannot be satisfied.
        if top.state == NOT_APPLICABLE:
            top = NodeResult(INCOMPLETE, [Outstanding(None, "No applicable requirements remain.")])
    else:
        top = NodeResult(INCOMPLETE, [Outstanding(None, "The plan has no requirements.")])

    return PlanResult(
        state=top.state,
        nodes=results,
        outstanding=top.outstanding,
        blocked=blocked,
        leaves_total=counts["total"],
        leaves_complete=counts["complete"],
        leaves_unresolved=counts["unresolved"],
    )
