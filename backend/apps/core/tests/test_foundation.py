"""
Foundation-phase tests.

These deliberately test infrastructure only: that the project boots,
that the database is reachable, and that the /api/v1/ mount point
responds. No domain/feature logic exists yet, so there is nothing
else to test at this phase.
"""

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class DatabaseConnectionTests(TestCase):
    def test_database_connection_is_alive(self):
        """The configured database is reachable and query-able."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            self.assertEqual(cursor.fetchone(), (1,))

    def test_database_engine_is_postgresql(self):
        """Foundation must run on PostgreSQL, not a fallback engine."""
        self.assertIn("postgresql", settings.DATABASES["default"]["ENGINE"])


class HealthCheckEndpointTests(APITestCase):
    def test_health_endpoint_is_reachable_without_authentication(self):
        """The health check must not require auth, unlike the API default."""
        url = reverse("core:health")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_endpoint_reports_database_status(self):
        url = reverse("core:health")
        response = self.client.get(url)
        self.assertEqual(response.data["status"], "ok")
        self.assertTrue(response.data["database"])

    def test_health_endpoint_is_mounted_under_api_v1(self):
        url = reverse("core:health")
        self.assertEqual(url, "/api/v1/core/health/")


class SecuritySettingsTests(TestCase):
    def test_secret_key_is_not_the_django_default_placeholder(self):
        self.assertFalse(settings.SECRET_KEY.startswith("django-insecure-"))

    def test_default_permission_is_authenticated(self):
        """
        API endpoints are locked down by default; individual views must
        explicitly opt in to public access (as the health check does).
        """
        self.assertIn(
            "rest_framework.permissions.IsAuthenticated",
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
        )

    def test_debug_is_off_under_production_settings(self):
        import importlib

        production_settings = importlib.import_module("config.settings.production")
        self.assertFalse(production_settings.DEBUG)


class InstalledAppsTests(TestCase):
    def test_rest_framework_is_installed(self):
        self.assertIn("rest_framework", settings.INSTALLED_APPS)

    def test_expected_feature_apps_are_installed(self):
        """
        Tracks which feature apps have been built so far. Update this
        list as each new phase adds its app — it is intentionally a
        strict equality check, not a subset check, so an app being
        added (or accidentally left out of settings) is caught here.
        """
        self.assertEqual(
            settings.LOCAL_APPS,
            [
                "apps.core",
                "apps.accounts",
                "apps.businesses",
                "apps.services",
                "apps.jobs",
                "apps.marketplace",
                "apps.search",
            ],
        )
