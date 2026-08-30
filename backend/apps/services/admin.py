from django.contrib import admin

from .models import Service, ServiceCategory


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "business",
        "category",
        "price",
        "price_type",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "price_type", "category"]
    search_fields = ["title", "business__name", "business__owner__email"]
    readonly_fields = ["slug", "created_at", "updated_at"]
