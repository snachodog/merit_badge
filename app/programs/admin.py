from django.contrib import admin

from .models import Award, AwardVersion, Program, ProgramOwner


@admin.register(ProgramOwner)
class ProgramOwnerAdmin(admin.ModelAdmin):
    list_display = ("name", "owner_type", "country_or_region", "default_language")
    list_filter = ("owner_type",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "program_type", "status", "is_custom", "visibility")
    list_filter = ("status", "is_custom", "owner")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class AwardVersionLink(admin.TabularInline):
    """Read-only list of an award's versions. Edit them on their own page."""

    model = AwardVersion
    extra = 0
    fields = ("version_label", "status", "published_at")
    readonly_fields = fields
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "award_type", "category", "status")
    list_filter = ("award_type", "status", "program")
    search_fields = ("name", "slug", "official_identifier")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AwardVersionLink]
