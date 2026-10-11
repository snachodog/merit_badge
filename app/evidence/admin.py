from django.contrib import admin

from .models import EvidenceRecord


@admin.register(EvidenceRecord)
class EvidenceRecordAdmin(admin.ModelAdmin):
    """Read-only: evidence is private to its owner and changes through services."""

    list_display = ("__str__", "evidence_type", "review_status", "created_at")
    list_filter = ("evidence_type", "review_status")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
