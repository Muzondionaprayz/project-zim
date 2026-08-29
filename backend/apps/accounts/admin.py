from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Admin for the custom, email-based User model.

    Overrides Django's default fieldsets/add form since there is no
    `username` field on this model.
    """

    ordering = ["-date_joined"]
    list_display = ["email", "role", "is_staff", "is_active", "date_joined"]
    list_filter = ["role", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    inlines = [UserProfileInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "role", "password1", "password2"),
            },
        ),
    )
