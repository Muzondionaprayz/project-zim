from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Read-mostly admin view. Status transitions should go through
    apps.reviews.services (and the dedicated API actions) so
    transition rules stay enforced in one place.
    """

    list_display = ["id", "reviewer", "target", "rating", "status", "created_at"]
    list_filter = ["status", "rating"]
    search_fields = ["reviewer__email", "body"]
    readonly_fields = ["status", "moderation_notes", "created_at", "updated_at"]
