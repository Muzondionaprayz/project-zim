from django.contrib import admin

from .models import ListingImage, MarketplaceCategory, MarketplaceListing


@admin.register(MarketplaceCategory)
class MarketplaceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0
    readonly_fields = ["is_primary", "created_at"]


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    """
    Read-mostly admin view. Status/moderation transitions should go
    through apps.marketplace.services (and the dedicated API
    actions) so transition rules stay enforced in one place.
    """

    list_display = [
        "title",
        "seller",
        "category",
        "status",
        "moderation_status",
        "price",
        "city",
        "province",
        "created_at",
    ]
    list_filter = ["status", "moderation_status", "category", "province"]
    search_fields = ["title", "seller__email", "city", "province"]
    readonly_fields = [
        "slug",
        "status",
        "moderation_status",
        "moderation_notes",
        "created_at",
        "updated_at",
    ]
    inlines = [ListingImageInline]
