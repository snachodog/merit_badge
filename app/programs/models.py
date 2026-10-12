"""Program definitions: owners, programs, awards and their versions.

Nothing here is specific to one organization. Choice values come from
PLAN.md section 6. Version immutability rules are described in
docs/decisions/0003-content-version-model.md.
"""
from django.core.exceptions import ValidationError
from django.db import models


class ImmutableVersionError(Exception):
    """Raised when code tries to change a published or archived version."""


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProgramOwner(TimestampedModel):
    class OwnerType(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        INDIVIDUAL = "individual", "Individual"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    owner_type = models.CharField(
        max_length=20, choices=OwnerType.choices, default=OwnerType.ORGANIZATION
    )
    website_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    country_or_region = models.CharField(max_length=100, blank=True)
    default_language = models.CharField(max_length=20, default="en")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Program(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    class Visibility(models.TextChoices):
        # Sharing and public values are future work (PLAN.md section 6.2).
        PRIVATE = "private", "Private"

    owner = models.ForeignKey(ProgramOwner, on_delete=models.PROTECT, related_name="programs")
    name = models.CharField(max_length=200)
    slug = models.SlugField()
    program_type = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_custom = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    # Catalog coverage (PLAN.md section 16, phase 3). Defaults claim nothing.
    catalog_source_url = models.URLField(
        blank=True, help_text="Where the owner publishes the list of entries."
    )
    catalog_expected_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How many entries the program has, if you know. Empty means unknown.",
    )
    catalog_validated_complete = models.BooleanField(
        default=False,
        help_text="Tick only after you checked every entry against its source.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="program_unique_slug_per_owner")
        ]

    def __str__(self):
        return self.name


class Award(TimestampedModel):
    """A badge, rank, adventure, certificate or custom achievement."""

    class AwardType(models.TextChoices):
        MERIT_BADGE = "merit_badge", "Merit badge"
        RANK = "rank", "Rank"
        ADVENTURE = "adventure", "Adventure"
        AWARD = "award", "Award"
        CERTIFICATE = "certificate", "Certificate"
        CUSTOM = "custom", "Custom"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="awards")
    name = models.CharField(max_length=200)
    slug = models.SlugField()
    award_type = models.CharField(
        max_length=20, choices=AwardType.choices, default=AwardType.CUSTOM
    )
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    official_identifier = models.CharField(max_length=100, blank=True)
    eligibility_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["program", "slug"], name="award_unique_slug_per_program")
        ]

    def __str__(self):
        return self.name


class AwardVersionQuerySet(models.QuerySet):
    """Blocks bulk changes that would bypass the model-level guards."""

    def _locked(self):
        return self.filter(status__in=AwardVersion.LOCKED_STATUSES)

    def update(self, **kwargs):
        if self._locked().exists():
            raise ImmutableVersionError("Published or archived versions cannot be changed.")
        return super().update(**kwargs)

    def delete(self):
        if self._locked().exists():
            raise ImmutableVersionError("Published or archived versions cannot be deleted.")
        return super().delete()


class AwardVersion(TimestampedModel):
    """One stable version of an award's requirement tree."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class SourceStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        USER_AUTHORED = "user_authored", "User-authored"
        REVIEWED = "reviewed", "Reviewed"
        VERIFIED = "verified", "Verified"
        DISPUTED = "disputed", "Disputed"

    class RightsStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        PERMISSION_CONFIRMED = "permission_confirmed", "Permission confirmed"
        LICENSED = "licensed", "Licensed"
        PUBLIC_DOMAIN = "public_domain", "Public domain"
        USER_AUTHORED = "user_authored", "User-authored"
        LINK_ONLY = "link_only", "Link only"

    LOCKED_STATUSES = (Status.PUBLISHED, Status.ARCHIVED)
    # Allowed status changes. Moving to published goes through the publish service.
    TRANSITIONS = {
        Status.DRAFT: {Status.REVIEW},
        Status.REVIEW: {Status.DRAFT, Status.PUBLISHED},
        Status.PUBLISHED: {Status.ARCHIVED},
        Status.ARCHIVED: set(),
    }

    award = models.ForeignKey(Award, on_delete=models.PROTECT, related_name="versions")
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revisions",
        help_text="The published version this draft was copied from.",
    )
    version_label = models.CharField(max_length=100)
    published_at = models.DateTimeField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_until = models.DateField(null=True, blank=True)
    source_checked_at = models.DateTimeField(null=True, blank=True)
    source_status = models.CharField(
        max_length=20, choices=SourceStatus.choices, default=SourceStatus.UNVERIFIED
    )
    rights_status = models.CharField(
        max_length=30, choices=RightsStatus.choices, default=RightsStatus.UNKNOWN
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    change_summary = models.TextField(blank=True)

    objects = AwardVersionQuerySet.as_manager()

    class Meta:
        ordering = ["award", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["award", "version_label"], name="version_unique_label_per_award"
            )
        ]

    def __str__(self):
        return f"{self.award} {self.version_label}"

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    def clean(self):
        if self.effective_from and self.effective_until and self.effective_until < self.effective_from:
            raise ValidationError("The end date must not be before the start date.")
        if self.previous_version_id and self.previous_version_id == self.pk:
            raise ValidationError("A version cannot be its own previous version.")

    def save(self, *args, **kwargs):
        stored_status = None
        if self.pk:
            stored = AwardVersion.objects.filter(pk=self.pk).values("status").first()
            stored_status = stored["status"] if stored else None
        if stored_status is None:
            if self.status != self.Status.DRAFT:
                raise ImmutableVersionError("A new version must start as a draft.")
        else:
            self._check_change_allowed(stored_status)
            if self.status == self.Status.PUBLISHED and stored_status != self.Status.PUBLISHED:
                if not getattr(self, "_publish_approved", False):
                    raise ImmutableVersionError(
                        "Use requirements.services.publish_version to publish a version."
                    )
        super().save(*args, **kwargs)

    def _check_change_allowed(self, stored_status):
        if stored_status in self.LOCKED_STATUSES:
            # The only allowed change is published -> archived, and nothing else.
            if stored_status == self.Status.PUBLISHED and self.status == self.Status.ARCHIVED:
                if self._differs_from_stored(ignore={"status", "updated_at"}):
                    raise ImmutableVersionError(
                        "Archiving a version cannot change any other field."
                    )
                return
            raise ImmutableVersionError(
                f"This version is {stored_status} and cannot be changed. "
                "Create a new revision instead."
            )
        if self.status != stored_status and self.status not in self.TRANSITIONS[stored_status]:
            raise ImmutableVersionError(
                f"A version cannot move from {stored_status} to {self.status}."
            )

    def _differs_from_stored(self, ignore):
        stored = AwardVersion.objects.get(pk=self.pk)
        for field in self._meta.concrete_fields:
            if field.attname in ignore:
                continue
            if getattr(stored, field.attname) != getattr(self, field.attname):
                return True
        return False

    def delete(self, *args, **kwargs):
        stored = AwardVersion.objects.filter(pk=self.pk).values("status").first()
        if stored and stored["status"] != self.Status.DRAFT and stored["status"] != self.Status.REVIEW:
            raise ImmutableVersionError("Published or archived versions cannot be deleted.")
        return super().delete(*args, **kwargs)
