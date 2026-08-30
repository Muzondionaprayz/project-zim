"""
/api/v1/ URL aggregator.

Each feature app owns its own urls.py; this module only wires them
together under the version prefix. Add one `path(...)` entry per app
as features are implemented (Accounts, etc.) — do not put endpoint
logic here.
"""

from django.urls import include, path

urlpatterns = [
    path("core/", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("businesses/", include("apps.businesses.urls")),
    path("services/", include("apps.services.urls")),
    path("jobs/", include("apps.jobs.urls")),
]
