from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.services import services
from apps.services.models import Service


class ActivateServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )

    def test_activate_service_on_approved_business_succeeds(self):
        business = Business.objects.create(
            owner=self.owner, name="Approved Biz", status=Business.Status.APPROVED
        )
        service = Service.objects.create(business=business, title="Svc", is_active=False)
        services.activate_service(service)
        service.refresh_from_db()
        self.assertTrue(service.is_active)

    def test_activate_service_on_non_approved_business_is_rejected(self):
        business = Business.objects.create(owner=self.owner, name="Draft Biz")
        service = Service.objects.create(business=business, title="Svc", is_active=False)
        with self.assertRaises(ValidationError):
            services.activate_service(service)
        service.refresh_from_db()
        self.assertFalse(service.is_active)

    def test_activate_service_on_suspended_business_is_rejected(self):
        business = Business.objects.create(
            owner=self.owner, name="Suspended Biz", status=Business.Status.SUSPENDED
        )
        service = Service.objects.create(business=business, title="Svc", is_active=False)
        with self.assertRaises(ValidationError):
            services.activate_service(service)


class DeactivateServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Approved Biz", status=Business.Status.APPROVED
        )

    def test_deactivate_active_service_succeeds(self):
        service = Service.objects.create(business=self.business, title="Svc", is_active=True)
        services.deactivate_service(service)
        service.refresh_from_db()
        self.assertFalse(service.is_active)

    def test_deactivate_already_inactive_service_is_idempotent(self):
        service = Service.objects.create(business=self.business, title="Svc", is_active=False)
        services.deactivate_service(service)  # should not raise
        service.refresh_from_db()
        self.assertFalse(service.is_active)
