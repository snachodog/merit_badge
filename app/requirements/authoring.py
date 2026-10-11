"""Manual editing of a draft requirement tree. Views call these functions.

The models refuse changes to published or archived versions. A version in
review is also treated as read-only here: return it to draft to edit it.
"""
from django.db import transaction

from programs.models import AwardVersion, ImmutableVersionError

from .models import RequirementActionTag, RequirementNode


def assert_editable(version):
    current = AwardVersion.objects.filter(pk=version.pk).values_list("status", flat=True).first()
    if current != AwardVersion.Status.DRAFT:
        raise ImmutableVersionError(
            f"The version is {current}. Only a draft can be edited. "
            "Return it to draft, or create a revision of a published version."
        )


def next_sort_order(version, parent):
    last = (
        RequirementNode.objects.filter(award_version=version, parent=parent)
        .order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
    )
    return 0 if last is None else last + 1


def set_action_tags(node, tags):
    """Make the node's tags equal `tags`. Tags chosen by a person count as reviewed."""
    wanted = set(tags)
    for existing in RequirementActionTag.objects.filter(node=node):
        if existing.tag not in wanted:
            existing.delete()
        elif not existing.reviewed:
            existing.reviewed = True
            existing.save()
        wanted.discard(existing.tag)
    for tag in sorted(wanted):
        RequirementActionTag.objects.create(node=node, tag=tag, reviewed=True)


@transaction.atomic
def save_node(node, version, parent, tags):
    """Create or update a node in a draft version."""
    assert_editable(version)
    if node.pk is None:
        node.award_version = version
        node.parent = parent
        node.sort_order = next_sort_order(version, parent)
    node.save()
    set_action_tags(node, tags)
    return node


@transaction.atomic
def delete_node(node):
    """Delete a node and everything below it."""
    assert_editable(node.award_version)
    node.delete()


@transaction.atomic
def move_node(node, direction):
    """Swap a node with its previous ('up') or next ('down') sibling. Returns True if moved."""
    assert_editable(node.award_version)
    siblings = list(
        RequirementNode.objects.filter(award_version=node.award_version_id, parent_id=node.parent_id)
        .order_by("sort_order", "id")
    )
    index = next(i for i, s in enumerate(siblings) if s.pk == node.pk)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(siblings):
        return False
    siblings[index], siblings[target] = siblings[target], siblings[index]
    for order, sibling in enumerate(siblings):  # renumber 0..n so orders stay unique
        if sibling.sort_order != order:
            sibling.sort_order = order
            sibling.save()
    return True
