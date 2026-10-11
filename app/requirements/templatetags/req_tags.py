from django import template

from requirements import tree_rules

register = template.Library()


@register.filter
def logic_label(node):
    """Plain-language label for how a group is completed. Empty for single requirements."""
    logic = node.completion_logic
    if logic == tree_rules.ALL:
        return "Complete all of these"
    if logic == tree_rules.ANY:
        return "Complete any one of these"
    if logic == tree_rules.CHOOSE_N:
        return f"Choose {node.completion_count} of these"
    if logic == tree_rules.SEQUENCE:
        return "Complete these in order"
    if logic == tree_rules.CONDITIONAL:
        cond = node.condition_expression or {}
        return f"If {cond.get('key', '?')} is {cond.get('equals', '?')}, complete these"
    return ""
