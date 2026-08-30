from django.contrib import admin

from .models import Job, JobApplication, JobCategory


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """
    Read-mostly admin view onto jobs. Status transitions should go
    through apps.jobs.services (and the dedicated API actions) so
    transition rules stay enforced in one place.
    """

    list_display = [
        "title",
        "employer",
        "category",
        "status",
        "job_type",
        "city",
        "province",
        "deadline",
        "created_at",
    ]
    list_filter = ["status", "job_type", "category", "province"]
    search_fields = ["title", "employer__email", "city", "province"]
    readonly_fields = ["slug", "status", "created_at", "updated_at"]


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ["job", "applicant", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["job__title", "applicant__email"]
    readonly_fields = ["status", "created_at", "updated_at"]
