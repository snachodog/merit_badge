"""Pure rules for requirement trees. No Django, no database.

Callers turn their nodes into `NodeSpec` objects and call `validate_tree`.
The rules are generic. They know about completion logic and nesting only,
nothing about any one organization (PLAN.md sections 6.5 and 7.1).

Logic types:
- single: a leaf with its own completion status. No children, no count.
- all, any, sequence: a group. Needs at least one child, no count.
- choose_n: a group. Needs a count from 1 to the number of children.
- conditional: a group. Needs at least one child and a condition
  expression. Shape: {"key": "<non-empty text>", "equals": <text, number or bool>}.
"""
from dataclasses import dataclass
from typing import Any, Hashable, Optional

SINGLE = "single"
ALL = "all"
ANY = "any"
CHOOSE_N = "choose_n"
SEQUENCE = "sequence"
CONDITIONAL = "conditional"

LOGIC_TYPES = (SINGLE, ALL, ANY, CHOOSE_N, SEQUENCE, CONDITIONAL)
GROUP_LOGIC_TYPES = (ALL, ANY, CHOOSE_N, SEQUENCE, CONDITIONAL)


@dataclass(frozen=True)
class NodeSpec:
    key: Hashable
    parent_key: Optional[Hashable] = None
    sort_order: int = 0
    display_number: str = ""
    completion_logic: str = SINGLE
    completion_count: Optional[int] = None
    condition_expression: Any = None


@dataclass(frozen=True)
class Issue:
    key: Optional[Hashable]
    path: str
    message: str

    def __str__(self):
        return f"{self.path}: {self.message}" if self.path else self.message


def check_condition_expression(expression):
    """Return a list of problems with a condition expression (empty if valid)."""
    if not isinstance(expression, dict):
        return ['The condition must be an object like {"key": "name", "equals": "value"}.']
    problems = []
    extra = set(expression) - {"key", "equals"}
    if extra:
        problems.append("The condition has unknown fields: " + ", ".join(sorted(extra)) + ".")
    key = expression.get("key")
    if not isinstance(key, str) or not key.strip():
        problems.append('The condition needs a non-empty text "key".')
    if "equals" not in expression:
        problems.append('The condition needs an "equals" value.')
    elif not isinstance(expression["equals"], (str, int, bool)) or expression["equals"] is None:
        problems.append('The "equals" value must be text, a number, or true/false.')
    return problems


def check_node_fields(logic, count, condition):
    """Checks that need only the node's own fields. Returns a list of messages."""
    if logic not in LOGIC_TYPES:
        return [f"Unknown completion logic: {logic!r}."]
    problems = []
    if logic == CHOOSE_N:
        if count is None or count < 1:
            problems.append("Choose N needs a count of at least 1.")
    elif count is not None:
        problems.append("A count is only allowed with Choose N.")
    if logic == CONDITIONAL:
        if condition in (None, ""):
            problems.append("A conditional node needs a condition.")
        else:
            problems.extend(check_condition_expression(condition))
    elif condition not in (None, ""):
        problems.append("A condition is only allowed with conditional logic.")
    return problems


def _label(node, by_key):
    """Readable path such as '1 > 1a' built from display numbers."""
    parts = []
    seen = set()
    current = node
    while current is not None and current.key not in seen:
        seen.add(current.key)
        parts.append(current.display_number or f"node {current.key}")
        current = by_key.get(current.parent_key)
    return " > ".join(reversed(parts))


def validate_tree(nodes):
    """Return a list of Issue objects. An empty list means the tree is valid."""
    nodes = list(nodes)
    issues = []
    if not nodes:
        return [Issue(None, "", "The version has no requirements.")]

    by_key = {}
    for n in nodes:
        if n.key in by_key:
            issues.append(Issue(n.key, "", f"Duplicate node key {n.key!r}."))
        by_key[n.key] = n

    children = {}
    for n in nodes:
        if n.parent_key is None:
            continue
        if n.parent_key not in by_key:
            issues.append(
                Issue(n.key, _label(n, by_key), "The parent is not part of this version.")
            )
            continue
        children.setdefault(n.parent_key, []).append(n)

    # Cycles: walk up from every node; a loop never reaches a root.
    for n in nodes:
        seen = set()
        current = n
        while current is not None and current.parent_key in by_key:
            if current.key in seen:
                issues.append(Issue(n.key, f"node {n.key}", "The parent links form a loop."))
                break
            seen.add(current.key)
            current = by_key[current.parent_key]

    # Unique sort_order among siblings (roots are siblings of each other).
    siblings = {}
    for n in nodes:
        siblings.setdefault(n.parent_key if n.parent_key in by_key else None, []).append(n)
    for group in siblings.values():
        counts = {}
        for n in group:
            counts.setdefault(n.sort_order, []).append(n)
        for order, same in counts.items():
            if len(same) > 1:
                for n in same:
                    issues.append(
                        Issue(
                            n.key,
                            _label(n, by_key),
                            f"Sort order {order} is used by more than one sibling.",
                        )
                    )

    for n in nodes:
        label = _label(n, by_key) if len(issues) < 10_000 else str(n.key)
        kids = children.get(n.key, [])
        if n.completion_logic not in LOGIC_TYPES:
            issues.append(Issue(n.key, label, f"Unknown completion logic: {n.completion_logic!r}."))
            continue
        for message in check_node_fields(
            n.completion_logic, n.completion_count, n.condition_expression
        ):
            issues.append(Issue(n.key, label, message))
        if n.completion_logic == SINGLE:
            if kids:
                issues.append(
                    Issue(n.key, label, "A single requirement cannot have child requirements.")
                )
        else:
            if not kids:
                issues.append(
                    Issue(n.key, label, f"Logic '{n.completion_logic}' needs at least one child.")
                )
            elif n.completion_logic == CHOOSE_N and n.completion_count is not None:
                if n.completion_count > len(kids):
                    issues.append(
                        Issue(
                            n.key,
                            label,
                            f"Choose {n.completion_count} but there are only {len(kids)} children.",
                        )
                    )
    return issues


def walk(nodes):
    """Yield (spec, depth) in display order: parents first, siblings by sort_order.

    Nodes whose parent is missing are treated as roots. Loops are not
    followed twice, so this is safe on bad data.
    """
    nodes = list(nodes)
    keys = {n.key for n in nodes}
    children = {}
    for n in nodes:
        parent = n.parent_key if n.parent_key in keys else None
        children.setdefault(parent, []).append(n)
    for group in children.values():
        group.sort(key=lambda n: (n.sort_order, str(n.key)))
    visited = set()

    def visit(parent, depth):
        for n in children.get(parent, []):
            if n.key in visited:
                continue
            visited.add(n.key)
            yield n, depth
            yield from visit(n.key, depth + 1)

    yield from visit(None, 0)
