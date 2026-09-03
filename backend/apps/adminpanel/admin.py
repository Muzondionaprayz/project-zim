from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only in the Django admin — entries are only ever created via log_action()."""

    list_display = ["action", "actor", "target_type", "target_id", "created_at"]
    list_filter = ["action", "target_type"]
    search_fields = ["actor__email", "action", "details"]
    readonly_fields = ["actor", "action", "target_type", "target_id", "details", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
