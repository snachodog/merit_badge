"""Pure tests for the completion engine. No database."""
from learning import completion as c
from learning.completion import COMPLETE, INCOMPLETE, NOT_APPLICABLE, UNRESOLVED
from requirements.tree_rules import NodeSpec

DONE = "personally_completed"


def S(key, parent=None, order=0, logic="single", count=None, cond=None):
    return NodeSpec(
        key=key, parent_key=parent, sort_order=order, display_number=str(key),
        completion_logic=logic, completion_count=count, condition_expression=cond,
    )


def run(nodes, done=(), answers=None, **kw):
    return c.evaluate(nodes, {k: DONE for k in done}, answers, **kw)


def test_single_needs_personal_completion():
    nodes = [S("a")]
    assert run(nodes).state == INCOMPLETE
    assert run(nodes, ["a"]).state == COMPLETE


def test_other_statuses_never_count():
    nodes = [S("a")]
    for status in ("in_progress", "ready_for_review", "awaiting_evidence", "needs_more_work",
                   "prior_knowledge", "not_applicable_by_explicit_rule"):
        assert c.evaluate(nodes, {"a": status}).state == INCOMPLETE


def test_all():
    nodes = [S("g", logic="all"), S("a", "g", 0), S("b", "g", 1)]
    assert run(nodes, ["a"]).state == INCOMPLETE
    res = run(nodes, ["a"])
    assert [o.key for o in res.outstanding] == ["b"]
    assert run(nodes, ["a", "b"]).state == COMPLETE


def test_any():
    nodes = [S("g", logic="any"), S("a", "g", 0), S("b", "g", 1)]
    res = run(nodes)
    assert res.state == INCOMPLETE and res.outstanding[0].key == "g"
    assert run(nodes, ["b"]).state == COMPLETE


def test_choose_n_counts():
    nodes = [S("g", logic="choose_n", count=2)] + [S(k, "g", i) for i, k in enumerate("abc")]
    assert run(nodes).state == INCOMPLETE
    res = run(nodes, ["a"])
    assert res.state == INCOMPLETE and "1 more" in res.outstanding[0].message
    assert run(nodes, ["a", "c"]).state == COMPLETE
    assert run(nodes, ["a", "b", "c"]).state == COMPLETE


def test_sequence_order_blocks_later_items():
    nodes = [S("g", logic="sequence"), S("a", "g", 0), S("b", "g", 1), S("c", "g", 2)]
    res = run(nodes)
    assert res.blocked == {"b": "a", "c": "a"}
    res = run(nodes, ["a"])
    assert res.blocked == {"c": "b"}
    assert run(nodes, ["a", "b", "c"]).state == COMPLETE
    assert run(nodes, ["a", "b", "c"]).blocked == {}


def test_sequence_out_of_order_data_is_not_complete():
    nodes = [S("g", logic="sequence"), S("a", "g", 0), S("b", "g", 1)]
    assert run(nodes, ["b"]).state == INCOMPLETE


def test_sequence_blocks_whole_subtree():
    nodes = [S("g", logic="sequence"), S("a", "g", 0), S("b", "g", 1, logic="all"),
             S("b1", "b", 0), S("b2", "b", 1)]
    assert run(nodes).blocked == {"b": "a", "b1": "a", "b2": "a"}


def test_conditional_unresolved_without_answer():
    cond = {"key": "has_pet", "equals": True}
    nodes = [S("g", logic="conditional", cond=cond), S("a", "g")]
    res = run(nodes)
    assert res.state == UNRESOLVED
    assert "has_pet" in res.outstanding[0].message


def test_conditional_true_acts_as_all():
    cond = {"key": "k", "equals": "yes"}
    nodes = [S("g", logic="conditional", cond=cond), S("a", "g", 0), S("b", "g", 1)]
    assert run(nodes, ["a"], {"k": "yes"}).state == INCOMPLETE
    assert run(nodes, ["a", "b"], {"k": "yes"}).state == COMPLETE


def test_conditional_false_branch_not_applicable_and_plan_needs_other_work():
    cond = {"key": "k", "equals": "yes"}
    nodes = [S("g", logic="conditional", cond=cond, order=0), S("a", "g"), S("z", order=1)]
    res = run(nodes, [], {"k": "no"})
    assert res.nodes["g"].state == NOT_APPLICABLE
    assert res.nodes["a"].state == NOT_APPLICABLE
    assert res.state == INCOMPLETE and [o.key for o in res.outstanding] == ["z"]
    assert run(nodes, ["z"], {"k": "no"}).state == COMPLETE


def test_conditional_answer_type_must_match():
    cond = {"key": "k", "equals": True}
    nodes = [S("g", logic="conditional", cond=cond), S("a", "g")]
    assert run(nodes, [], {"k": 1}).nodes["g"].state == NOT_APPLICABLE


def test_not_applicable_leaves_do_not_count_in_summary():
    cond = {"key": "k", "equals": "yes"}
    nodes = [S("g", logic="conditional", cond=cond, order=0), S("a", "g"), S("z", order=1)]
    res = run(nodes, ["z"], {"k": "no"})
    assert (res.leaves_total, res.leaves_complete) == (1, 1)


def test_nested_all_any_choose():
    # 1 (all): 1a, 1b (choose 2 of 3: x,y,z), 1c (any: p,q)
    nodes = [
        S("1", logic="all"),
        S("1a", "1", 0),
        S("1b", "1", 1, logic="choose_n", count=2),
        S("x", "1b", 0), S("y", "1b", 1), S("z", "1b", 2),
        S("1c", "1", 2, logic="any"),
        S("p", "1c", 0), S("q", "1c", 1),
    ]
    assert run(nodes, ["1a", "x", "y"]).state == INCOMPLETE
    assert run(nodes, ["1a", "x", "y", "q"]).state == COMPLETE
    assert run(nodes, ["x", "y", "z", "p"]).state == INCOMPLETE
    res = run(nodes, ["1a", "x", "p"])
    assert res.nodes["1b"].state == INCOMPLETE and res.nodes["1c"].state == COMPLETE


def test_unresolved_inside_all_does_not_hide_incomplete():
    cond = {"key": "k", "equals": 1}
    nodes = [S("g", logic="all"), S("a", "g", 0), S("c", "g", 1, logic="conditional", cond=cond),
             S("c1", "c", 0)]
    assert run(nodes, ["a"]).state == UNRESOLVED
    assert run(nodes, []).state == INCOMPLETE


def test_choose_n_unresolved_when_condition_could_decide():
    cond = {"key": "k", "equals": 1}
    nodes = [S("g", logic="any"), S("a", "g", 0), S("c", "g", 1, logic="conditional", cond=cond),
             S("c1", "c")]
    assert run(nodes).state == UNRESOLVED
    assert run(nodes, ["a"]).state == COMPLETE


def test_ignored_note_nodes_do_not_block():
    nodes = [S("n"), S("a", order=1)]
    assert run(nodes, ["a"], ignored_keys={"n"}).state == COMPLETE


def test_empty_plan_is_not_satisfied():
    assert run([]).state == INCOMPLETE
    assert not run([]).satisfied


def test_prior_knowledge_has_no_input_to_the_engine():
    # The engine reads statuses only. A claim cannot be passed in.
    import inspect
    assert "prior" not in " ".join(inspect.signature(c.evaluate).parameters)
