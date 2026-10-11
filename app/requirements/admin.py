from django.contrib import admin, messages

from programs.models import AwardVersion

from . import services
from .models import RequirementActionTag, RequirementNode, SourceRecord


def _version_is_open(version):
    return version is None or not version.is_locked


class ActionTagInline(admin.TabularInline):
    model = RequirementActionTag
    extra = 0

    def _open(self, obj):
        return obj is None or _version_is_open(obj.award_version)

    def has_add_permission(self, request, obj=None):
        return self._open(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._open(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._open(obj) and super().has_delete_permission(request, obj)


@admin.register(SourceRecord)
class SourceRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "publisher_or_creator", "source_type", "review_status")
    list_filter = ("source_type", "review_status")
    search_fields = ("title", "publisher_or_creator", "url")


@admin.register(RequirementNode)
class RequirementNodeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "award_version", "parent", "sort_order", "completion_logic")
    list_filter = ("completion_logic", "node_type", "text_origin")
    search_fields = ("display_number", "text")
    raw_id_fields = ("award_version", "parent", "source")
    inlines = [ActionTagInline]

    def has_change_permission(self, request, obj=None):
        return (obj is None or _version_is_open(obj.award_version)) and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return (obj is None or _version_is_open(obj.award_version)) and super().has_delete_permission(
            request, obj
        )


class RequirementNodeInline(admin.TabularInline):
    """Flat, ordered editing of one version's nodes. Pick a parent to nest."""

    model = RequirementNode
    fk_name = "award_version"
    extra = 0
    ordering = ("parent_id", "sort_order", "id")
    fields = (
        "display_number",
        "parent",
        "sort_order",
        "node_type",
        "text",
        "text_origin",
        "source",
        "completion_logic",
        "completion_count",
        "condition_expression",
    )
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "parent":
            version_id = request.resolver_match.kwargs.get("object_id")
            if version_id and field is not None:
                field.queryset = RequirementNode.objects.filter(award_version_id=version_id)
            elif field is not None:
                field.queryset = RequirementNode.objects.none()
        return field

    def _open(self, obj):
        return obj is None or not obj.is_locked

    def has_add_permission(self, request, obj=None):
        return self._open(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._open(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._open(obj) and super().has_delete_permission(request, obj)


@admin.register(AwardVersion)
class AwardVersionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "source_status", "rights_status", "published_at")
    list_filter = ("status", "source_status", "rights_status")
    search_fields = ("version_label", "award__name")
    readonly_fields = ("status", "published_at", "previous_version")
    inlines = [RequirementNodeInline]
    actions = ["submit_for_review", "publish", "create_revision", "archive"]

    def has_change_permission(self, request, obj=None):
        # Published and archived versions open as read-only pages.
        if obj is not None and obj.is_locked:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_locked:
            return False
        return super().has_delete_permission(request, obj)

    def _run(self, request, queryset, func, done):
        for version in queryset:
            try:
                func(version)
            except services.PublishError as exc:
                for problem in exc.problems:
                    self.message_user(request, f"{version}: {problem}", messages.ERROR)
            except services.WorkflowError as exc:
                self.message_user(request, f"{version}: {exc}", messages.ERROR)
            else:
                self.message_user(request, f"{version}: {done}", messages.SUCCESS)

    @admin.action(description="Submit selected drafts for review")
    def submit_for_review(self, request, queryset):
        self._run(request, queryset, services.submit_for_review, "submitted for review.")

    @admin.action(description="Publish selected versions that are in review")
    def publish(self, request, queryset):
        self._run(request, queryset, services.publish_version, "published.")

    @admin.action(description="Create a new draft revision from selected published versions")
    def create_revision(self, request, queryset):
        self._run(request, queryset, services.create_revision, "new draft revision created.")

    @admin.action(description="Archive selected published versions")
    def archive(self, request, queryset):
        self._run(request, queryset, services.archive_version, "archived.")
