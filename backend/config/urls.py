"""
Root URL configuration for Project Zim.

Only two things live here: the Django admin, and the versioned API
mount point. All actual API routes are defined under api/v1/urls.py
and each feature app's own urls.py, keeping this file stable as
features are added.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.v1.urls")),
]
