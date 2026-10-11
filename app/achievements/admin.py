from django.contrib import admin

from .models import AchievementRecord, LearnerProfile


@admin.register(AchievementRecord)
class AchievementRecordAdmin(admin.ModelAdmin):
    """Read-only: records come only from the plan completion flow."""

    list_display = ("display_title", "learner_display_name", "completed_at", "completion_basis")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name")
