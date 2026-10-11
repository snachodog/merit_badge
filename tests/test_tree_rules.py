"""Pure tree rules: no database needed."""
import pytest

from requirements import tree_rules as tr
from requirements.tree_rules import NodeSpec, validate_tree


def n(key, parent=None, order=0, logic=tr.SINGLE, count=None, cond=None, num=""):
    return NodeSpec(key, parent, order, num or str(key), logic, count, cond)


def messages(nodes):
    return [i.message for i in validate_tree(nodes)]


def test_empty_tree_is_invalid():
    assert messages([]) == ["The version has no requirements."]


def test_single_leaf_is_valid():
    assert validate_tree([n(1)]) == []


def test_single_with_children_is_invalid():
    issues = messages([n(1), n(2, parent=1)])
    assert any("single requirement cannot have child" in m for m in issues)


def test_single_with_count_is_invalid():
    assert any("only allowed with Choose N" in m for m in messages([n(1, count=2)]))


@pytest.mark.parametrize("logic", [tr.ALL, tr.ANY, tr.SEQUENCE])
def test_group_logic_valid_with_children(logic):
    assert validate_tree([n(1, logic=logic), n(2, 1, 0), n(3, 1, 1)]) == []


@pytest.mark.parametrize("logic", [tr.ALL, tr.ANY, tr.SEQUENCE, tr.CHOOSE_N])
def test_group_without_children_is_invalid(logic):
    count = 1 if logic == tr.CHOOSE_N else None
    assert any("needs at least one child" in m for m in messages([n(1, logic=logic, count=count)]))


@pytest.mark.parametrize("logic", [tr.ALL, tr.ANY, tr.SEQUENCE])
def test_count_rejected_outside_choose_n(logic):
    nodes = [n(1, logic=logic, count=1), n(2, 1)]
    assert any("only allowed with Choose N" in m for m in messages(nodes))


def test_choose_n_valid_range():
    for count in (1, 2, 3):
        nodes = [n(1, logic=tr.CHOOSE_N, count=count), n(2, 1, 0), n(3, 1, 1), n(4, 1, 2)]
        assert validate_tree(nodes) == []


@pytest.mark.parametrize("count", [None, 0])
def test_choose_n_needs_count_of_one_or_more(count):
    nodes = [n(1, logic=tr.CHOOSE_N, count=count), n(2, 1)]
    assert any("count of at least 1" in m for m in messages(nodes))


def test_choose_n_count_cannot_exceed_children():
    nodes = [n(1, logic=tr.CHOOSE_N, count=3), n(2, 1, 0), n(3, 1, 1)]
    assert any("only 2 children" in m for m in messages(nodes))


def test_conditional_valid():
    nodes = [n(1, logic=tr.CONDITIONAL, cond={"key": "age", "equals": "adult"}), n(2, 1)]
    assert validate_tree(nodes) == []


@pytest.mark.parametrize(
    "cond",
    [None, {}, {"key": "", "equals": 1}, {"key": "a"}, {"key": "a", "equals": [1]},
     {"key": "a", "equals": 1, "extra": 2}, "text"],
)
def test_conditional_needs_valid_condition(cond):
    assert validate_tree([n(1, logic=tr.CONDITIONAL, cond=cond), n(2, 1)])


def test_condition_not_allowed_without_conditional_logic():
    nodes = [n(1, logic=tr.ALL, cond={"key": "a", "equals": 1}), n(2, 1)]
    assert any("only allowed with conditional" in m for m in messages(nodes))


def test_unknown_logic_is_invalid():
    assert any("Unknown completion logic" in m for m in messages([n(1, logic="maybe")]))


def test_parent_must_be_in_same_version():
    assert any("parent is not part" in m for m in messages([n(1, parent=99)]))


def test_cycle_is_invalid():
    nodes = [n(1, parent=2, logic=tr.ALL), n(2, parent=1, logic=tr.ALL)]
    assert any("loop" in m for m in messages(nodes))


def test_duplicate_sibling_sort_order_is_invalid():
    nodes = [n(1, logic=tr.ALL), n(2, 1, 0), n(3, 1, 0)]
    assert any("Sort order 0" in m for m in messages(nodes))


def test_issue_path_uses_display_numbers():
    nodes = [n(1, logic=tr.ALL, num="1"), n(2, 1, 0, num="1a", logic=tr.ALL)]
    issue = validate_tree(nodes)[0]
    assert issue.path == "1 > 1a"


def test_walk_is_depth_first_by_sort_order():
    nodes = [
        n(1, logic=tr.ALL, order=1),
        n(2, 1, 1),
        n(3, 1, 0),
        n(4, order=0),
    ]
    assert [(s.key, d) for s, d in tr.walk(nodes)] == [(4, 0), (1, 0), (3, 1), (2, 1)]


def test_walk_survives_cycles():
    nodes = [n(1, parent=2), n(2, parent=1)]
    assert list(tr.walk(nodes)) == []
