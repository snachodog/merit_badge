"""Version workflow and tree services. Views and admin call these, not the models.

Status path: draft -> review -> published -> archived.
Published versions never change. A correction is a new draft revision
copied from the published version (`create_revision`).
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from programs.models import AwardVersion

from . import tree_rules
from .models import RequirementActionTag, RequirementNode


class PublishError(Exception):
    """The version cannot be published. `problems` lists every reason."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class WorkflowError(Exception):
    """The requested status change is not allowed from the current status."""


def node_specs(version):
    """Load a version's nodes as pure NodeSpec objects (one query)."""
    rows = RequirementNode.objects.filter(award_version=version).values(
        "id",
        "parent_id",
        "sort_order",
        "display_number",
        "completion_logic",
        "completion_count",
        "condition_expression",
    )
    return [
        tree_rules.NodeSpec(
            key=r["id"],
            parent_key=r["parent_id"],
            sort_order=r["sort_order"],
            display_number=r["display_number"],
            completion_logic=r["completion_logic"],
            completion_count=r["completion_count"],
            condition_expression=r["condition_expression"],
        )
        for r in rows
    ]


def validate_version_tree(version):
    return tree_rules.validate_tree(node_specs(version))


@dataclass
class TreeItem:
    node: RequirementNode
    depth: int
    children: list = field(default_factory=list)


def get_tree(version):
    """Return the version's nodes as nested TreeItem objects (roots, in display order)."""
    nodes = {
        n.pk: n
        for n in RequirementNode.objects.filter(award_version=version)
        .select_related("source")
        .prefetch_related("action_tags")
    }
    items = {pk: TreeItem(node=n, depth=0) for pk, n in nodes.items()}
    roots = []
    for spec, depth in tree_rules.walk(node_specs(version)):
        item = items[spec.key]
        item.depth = depth
        parent = items.get(spec.parent_key)
        (parent.children if parent else roots).append(item)
    return roots


def iter_tree(version):
    """Yield (node, depth) in display order."""
    nodes = {n.pk: n for n in RequirementNode.objects.filter(award_version=version)}
    for spec, depth in tree_rules.walk(node_specs(version)):
        yield nodes[spec.key], depth


def provenance_problems(version):
    """Rules from PLAN.md 14.1 and 6.4 for official-source text.

    Official-source nodes need a SourceRecord and a known rights status.
    If either is missing, the version must say so by being marked unverified.
    """
    official = RequirementNode.objects.filter(
        award_version=version, text_origin=RequirementNode.TextOrigin.OFFICIAL_SOURCE
    )
    if not official.exists():
        return []
    if version.source_status == AwardVersion.SourceStatus.UNVERIFIED:
        return []
    problems = []
    missing = official.filter(source__isnull=True).count()
    if missing:
        problems.append(
            f"{missing} official-source requirement(s) have no source record. "
            "Add a source or mark the version as unverified."
        )
    if version.rights_status == AwardVersion.RightsStatus.UNKNOWN:
        problems.append(
            "Official-source text needs a rights status. "
            "Set one or mark the version as unverified."
        )
    return problems


def publish_problems(version):
    problems = [str(i) for i in validate_version_tree(version)]
    problems.extend(provenance_problems(version))
    return problems


def _transition(version, target, allowed_from):
    with transaction.atomic():
        locked = AwardVersion.objects.select_for_update().get(pk=version.pk)
        if locked.status not in allowed_from:
            raise WorkflowError(
                f"A {locked.status} version cannot move to {target}."
            )
        locked.status = target
        return locked


def submit_for_review(version):
    locked = _transition(version, AwardVersion.Status.REVIEW, {AwardVersion.Status.DRAFT})
    locked.save()
    version.status = locked.status
    return version


def return_to_draft(version):
    locked = _transition(version, AwardVersion.Status.DRAFT, {AwardVersion.Status.REVIEW})
    locked.save()
    version.status = locked.status
    return version


def publish_version(version, when=None):
    """Publish a version that is in review, if its tree and provenance are valid."""
    with transaction.atomic():
        locked = AwardVersion.objects.select_for_update().get(pk=version.pk)
        if locked.status != AwardVersion.Status.REVIEW:
            raise WorkflowError("Only a version in review can be published.")
        problems = publish_problems(locked)
        if problems:
            raise PublishError(problems)
        locked.status = AwardVersion.Status.PUBLISHED
        locked.published_at = when or timezone.now()
        locked._publish_approved = True
        locked.save()
    version.status = locked.status
    version.published_at = locked.published_at
    return version


def archive_version(version):
    with transaction.atomic():
        locked = AwardVersion.objects.select_for_update().get(pk=version.pk)
        if locked.status != AwardVersion.Status.PUBLISHED:
            raise WorkflowError("Only a published version can be archived.")
        locked.status = AwardVersion.Status.ARCHIVED
        locked.save()
    version.status = locked.status
    return version


def _next_label(award, base):
    n = 1
    while True:
        label = f"{base}-rev{n}"
        if not AwardVersion.objects.filter(award=award, version_label=label).exists():
            return label
        n += 1


@transaction.atomic
def create_revision(version, version_label=None, change_summary=""):
    """Copy a published version into a new draft that links back to it."""
    source = AwardVersion.objects.select_for_update().get(pk=version.pk)
    if source.status != AwardVersion.Status.PUBLISHED:
        raise WorkflowError("A revision can only be made from a published version.")
    draft = AwardVersion.objects.create(
        award=source.award,
        previous_version=source,
        version_label=version_label or _next_label(source.award, source.version_label),
        source_checked_at=source.source_checked_at,
        source_status=source.source_status,
        rights_status=source.rights_status,
        change_summary=change_summary,
        status=AwardVersion.Status.DRAFT,
    )
    old_nodes = list(RequirementNode.objects.filter(award_version=source).order_by("id"))
    copies = {}
    # Parents first, so every parent has a new id before its children are made.
    pending = list(old_nodes)
    while pending:
        remaining = []
        for old in pending:
            if old.parent_id is not None and old.parent_id not in copies:
                remaining.append(old)
                continue
            copies[old.pk] = RequirementNode.objects.create(
                award_version=draft,
                parent=copies.get(old.parent_id),
                sort_order=old.sort_order,
                display_number=old.display_number,
                node_type=old.node_type,
                text=old.text,
                text_origin=old.text_origin,
                source_id=old.source_id,
                completion_logic=old.completion_logic,
                completion_count=old.completion_count,
                condition_expression=old.condition_expression,
                estimated_effort=old.estimated_effort,
                safety_notes=old.safety_notes,
            )
        if len(remaining) == len(pending):  # unreachable parent: stop, do not loop forever
            raise WorkflowError("The requirement tree has a broken parent link.")
        pending = remaining
    RequirementActionTag.objects.bulk_create(
        RequirementActionTag(node=copies[t.node_id], tag=t.tag, reviewed=t.reviewed)
        for t in RequirementActionTag.objects.filter(node__award_version=source)
    )
    return draft
