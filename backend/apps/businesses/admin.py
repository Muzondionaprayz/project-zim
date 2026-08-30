from django.contrib import admin

from .models import Business, BusinessCategory


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    """
    Read-mostly admin view onto businesses.

    Verification fields are intentionally read-only here — status
    transitions should go through apps.businesses.services (and, in
    a later phase, the dedicated admin API actions) so transition
    rules stay enforced in one place rather than being bypassable
    from the Django admin.
    """

    list_display = ["name", "owner", "category", "status", "city", "province", "created_at"]
    list_filter = ["status", "category", "province"]
    search_fields = ["name", "owner__email", "city", "province"]
    readonly_fields = [
        "slug",
        "status",
        "verification_notes",
        "submitted_at",
        "verified_at",
        "created_at",
        "updated_at",
    ]
