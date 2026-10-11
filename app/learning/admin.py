from django.contrib import admin

from .models import LearningPlan, PlanStatusLog, RequirementProgress


class ReadOnlyAdmin(admin.ModelAdmin):
    """Plans change through services, which enforce the completion rules."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LearningPlan)
class LearningPlanAdmin(ReadOnlyAdmin):
    list_display = ("title", "user", "award_version", "status", "started_at")
    list_filter = ("status",)


@admin.register(RequirementProgress)
class RequirementProgressAdmin(ReadOnlyAdmin):
    list_display = ("requirement_node", "learning_plan", "status")
    list_filter = ("status",)


@admin.register(PlanStatusLog)
class PlanStatusLogAdmin(ReadOnlyAdmin):
    list_display = ("plan", "from_status", "to_status", "changed_at")
