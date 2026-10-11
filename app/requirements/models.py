"""Requirement trees and their provenance.

Nodes belong to one AwardVersion. Once that version is published or
archived, nodes cannot be created, changed or deleted (see ADR 0003).
Tree-wide rules live in requirements/tree_rules.py and run when a version
is published.
"""
from django.core.exceptions import ValidationError
from django.db import models

from programs.models import AwardVersion, ImmutableVersionError, TimestampedModel

from . import tree_rules


class SourceRecord(TimestampedModel):
    class SourceType(models.TextChoices):
        OFFICIAL_PUBLICATION = "official_publication", "Official publication"
        OFFICIAL_WEB_PAGE = "official_web_page", "Official web page"
        USER_UPLOAD = "user_upload", "User upload"
        EXTERNAL_EDUCATIONAL = "external_educational", "External educational material"
        USER_AUTHORED = "user_authored", "User-authored"
        OTHER = "other", "Other"

    class ReviewStatus(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        REVIEWED = "reviewed", "Reviewed"
        VERIFIED = "verified", "Verified"
        DISPUTED = "disputed", "Disputed"

    title = models.CharField(max_length=300)
    publisher_or_creator = models.CharField(max_length=200, blank=True)
    url = models.URLField(blank=True)
    source_type = models.CharField(
        max_length=30, choices=SourceType.choices, default=SourceType.OTHER
    )
    retrieved_at = models.DateTimeField(null=True, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    license_or_permission_notes = models.TextField(blank=True)
    attribution_requirements = models.TextField(blank=True)
    access_notes = models.TextField(blank=True)
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.UNREVIEWED
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


def _assert_version_open(version_id):
    """Raise unless the version is still editable. Reads the database, not a cached object."""
    status = AwardVersion.objects.filter(pk=version_id).values_list("status", flat=True).first()
    if status in AwardVersion.LOCKED_STATUSES:
        raise ImmutableVersionError(
            f"The version is {status}; its requirements cannot be changed. "
            "Create a new revision instead."
        )


class RequirementNodeQuerySet(models.QuerySet):
    def _locked(self):
        return self.filter(award_version__status__in=AwardVersion.LOCKED_STATUSES)

    def update(self, **kwargs):
        if self._locked().exists():
            raise ImmutableVersionError("Requirements of a published version cannot be changed.")
        return super().update(**kwargs)

    def delete(self):
        if self._locked().exists():
            raise ImmutableVersionError("Requirements of a published version cannot be deleted.")
        return super().delete()

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for version_id in {o.award_version_id for o in objs}:
            _assert_version_open(version_id)
        return super().bulk_create(objs, *args, **kwargs)


class RequirementNode(TimestampedModel):
    class NodeType(models.TextChoices):
        ATOMIC = "atomic", "Requirement"
        GROUP = "group", "Group"
        NOTE = "note", "Note"

    class TextOrigin(models.TextChoices):
        OFFICIAL_SOURCE = "official_source", "Official-source transcription"
        USER_PROVIDED = "user_provided", "User-provided"
        APP_AUTHORED = "app_authored", "App-authored"
        OTHER = "other", "Other"

    # Values come from tree_rules so the pure module needs no Django.
    class CompletionLogic(models.TextChoices):
        SINGLE = tree_rules.SINGLE, "Single"
        ALL = tree_rules.ALL, "All of"
        ANY = tree_rules.ANY, "Any of"
        CHOOSE_N = tree_rules.CHOOSE_N, "Choose N"
        SEQUENCE = tree_rules.SEQUENCE, "In sequence"
        CONDITIONAL = tree_rules.CONDITIONAL, "Conditional"

    award_version = models.ForeignKey(
        AwardVersion, on_delete=models.CASCADE, related_name="nodes"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    sort_order = models.PositiveIntegerField(default=0)
    # Text, not a number: preserves "1", "1a" and "3b(2)" exactly as the source shows them.
    display_number = models.CharField(max_length=50, blank=True)
    node_type = models.CharField(max_length=10, choices=NodeType.choices, default=NodeType.ATOMIC)
    text = models.TextField(blank=True, help_text="Authoritative requirement wording.")
    text_origin = models.CharField(
        max_length=20, choices=TextOrigin.choices, default=TextOrigin.USER_PROVIDED
    )
    source = models.ForeignKey(
        SourceRecord, null=True, blank=True, on_delete=models.PROTECT, related_name="nodes"
    )
    completion_logic = models.CharField(
        max_length=12, choices=CompletionLogic.choices, default=CompletionLogic.SINGLE
    )
    completion_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="Used only with Choose N."
    )
    condition_expression = models.JSONField(
        null=True,
        blank=True,
        help_text='Conditional nodes only. Shape: {"key": "name", "equals": "value"}.',
    )
    estimated_effort = models.CharField(
        max_length=200, blank=True, help_text="An estimate, not part of the requirement."
    )
    safety_notes = models.TextField(blank=True)

    objects = RequirementNodeQuerySet.as_manager()

    class Meta:
        ordering = ["award_version", "parent_id", "sort_order", "id"]
        indexes = [models.Index(fields=["award_version", "parent", "sort_order"])]

    def __str__(self):
        label = self.display_number or f"#{self.pk}"
        return f"{label} {self.text[:50]}".strip()

    def clean(self):
        errors = {}
        if self.parent_id and self.parent_id == self.pk:
            errors["parent"] = "A requirement cannot be its own parent."
        elif self.parent_id and self.parent.award_version_id != self.award_version_id:
            errors["parent"] = "The parent must belong to the same version."
        for message in tree_rules.check_node_fields(
            self.completion_logic, self.completion_count, self.condition_expression
        ):
            errors.setdefault("completion_logic", message)
        if self.award_version_id:
            status = AwardVersion.objects.filter(pk=self.award_version_id).values_list(
                "status", flat=True
            ).first()
            if status in AwardVersion.LOCKED_STATUSES:
                errors["award_version"] = "This version is published and cannot be changed."
        if errors:
            raise ValidationError(errors)

    def _check_parent(self):
        if self.parent_id and self.parent.award_version_id != self.award_version_id:
            raise ValidationError({"parent": "The parent must belong to the same version."})

    def save(self, *args, **kwargs):
        self._check_parent()
        _assert_version_open(self.award_version_id)
        if self.pk:
            # Also block moving a node out of a locked version.
            old = RequirementNode.objects.filter(pk=self.pk).values_list(
                "award_version_id", flat=True
            ).first()
            if old is not None and old != self.award_version_id:
                _assert_version_open(old)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _assert_version_open(self.award_version_id)
        return super().delete(*args, **kwargs)


class RequirementActionTag(models.Model):
    """Workflow hint for a node. Never replaces the authoritative text."""

    class Tag(models.TextChoices):
        READ = "read", "Read"
        DISCUSS = "discuss", "Discuss"
        EXPLAIN = "explain", "Explain"
        DESCRIBE = "describe", "Describe"
        DEMONSTRATE = "demonstrate", "Demonstrate"
        SHOW = "show", "Show"
        MAKE = "make", "Make"
        BUILD = "build", "Build"
        PLAN = "plan", "Plan"
        PREPARE = "prepare", "Prepare"
        CONDUCT = "conduct", "Conduct"
        PARTICIPATE = "participate", "Participate"
        TEACH = "teach", "Teach"
        INTERVIEW = "interview", "Interview"
        VISIT = "visit", "Visit"
        OBSERVE = "observe", "Observe"
        RECORD = "record", "Record"
        LOG = "log", "Log"
        RESEARCH = "research", "Research"
        REFLECT = "reflect", "Reflect"
        CALCULATE = "calculate", "Calculate"
        IDENTIFY = "identify", "Identify"
        COMPARE = "compare", "Compare"
        OTHER = "other", "Other"

    node = models.ForeignKey(RequirementNode, on_delete=models.CASCADE, related_name="action_tags")
    tag = models.CharField(max_length=20, choices=Tag.choices)
    reviewed = models.BooleanField(
        default=False, help_text="A person confirmed this tag. Tags are never set by NLP alone."
    )

    class Meta:
        ordering = ["node", "tag"]
        constraints = [
            models.UniqueConstraint(fields=["node", "tag"], name="actiontag_unique_per_node")
        ]

    def __str__(self):
        return self.tag

    def save(self, *args, **kwargs):
        _assert_version_open(self.node.award_version_id)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _assert_version_open(self.node.award_version_id)
        return super().delete(*args, **kwargs)


class ImportRecord(TimestampedModel):
    """Remembers which JSON import created a draft, so repeating it is safe."""

    import_key = models.CharField(max_length=300, unique=True)
    content_sha256 = models.CharField(max_length=64)
    award_version = models.ForeignKey(
        AwardVersion, null=True, on_delete=models.SET_NULL, related_name="import_records"
    )

    def __str__(self):
        return self.import_key
