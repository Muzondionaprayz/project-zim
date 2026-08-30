from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.services.models import Service, ServiceCategory


class ServiceCategoryModelTests(TestCase):
    def test_slug_is_auto_generated_from_name(self):
        category = ServiceCategory.objects.create(name="Home Repairs & Maintenance")
        self.assertEqual(category.slug, "home-repairs-maintenance")

    def test_explicit_slug_is_preserved(self):
        category = ServiceCategory.objects.create(name="Haircuts", slug="hair")
        self.assertEqual(category.slug, "hair")

    def test_str_returns_name(self):
        category = ServiceCategory.objects.create(name="Catering")
        self.assertEqual(str(category), "Catering")


class ServiceModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(owner=self.owner, name="Jane's Biz")
        self.category = ServiceCategory.objects.create(name="Catering")

    def test_service_defaults_to_active(self):
        service = Service.objects.create(business=self.business, title="Wedding Catering")
        self.assertTrue(service.is_active)

    def test_service_defaults_to_quote_price_type(self):
        service = Service.objects.create(business=self.business, title="Wedding Catering")
        self.assertEqual(service.price_type, Service.PriceType.QUOTE)

    def test_slug_is_auto_generated_from_title(self):
        service = Service.objects.create(business=self.business, title="Wedding Catering")
        self.assertTrue(service.slug.startswith("wedding-catering"))

    def test_duplicate_titles_get_unique_slugs(self):
        first = Service.objects.create(business=self.business, title="Haircut")
        second_owner = User.objects.create_user(
            email="owner2@example.com", password="a-strong-passw0rd!"
        )
        second_business = Business.objects.create(owner=second_owner, name="Other Biz")
        second = Service.objects.create(business=second_business, title="Haircut")
        self.assertNotEqual(first.slug, second.slug)

    def test_is_publicly_visible_requires_active_and_approved_business(self):
        service = Service.objects.create(business=self.business, title="Draft Business Service")
        # Business defaults to draft, service defaults to active.
        self.assertFalse(service.is_publicly_visible)

        self.business.status = Business.Status.APPROVED
        self.business.save()
        service.refresh_from_db()
        self.assertTrue(service.is_publicly_visible)

        service.is_active = False
        service.save()
        self.assertFalse(service.is_publicly_visible)

    def test_deleting_category_sets_null_not_cascade(self):
        service = Service.objects.create(
            business=self.business, title="Cat Service", category=self.category
        )
        self.category.delete()
        service.refresh_from_db()
        self.assertIsNone(service.category)

    def test_deleting_business_deletes_service(self):
        service = Service.objects.create(business=self.business, title="Doomed Service")
        service_id = service.id
        self.business.delete()
        self.assertFalse(Service.objects.filter(id=service_id).exists())

    def test_negative_price_fails_validation(self):
        service = Service(business=self.business, title="Bad Price", price=Decimal("-5.00"))
        with self.assertRaises(ValidationError):
            service.full_clean()

    def test_zero_price_is_valid(self):
        service = Service(business=self.business, title="Free Consult", price=Decimal("0.00"))
        service.full_clean()  # should not raise

    def test_str_returns_title(self):
        service = Service.objects.create(business=self.business, title="String Service")
        self.assertEqual(str(service), "String Service")

    def test_service_has_no_owner_field(self):
        """
        Ownership must always be transitive through business.owner —
        there must be no independent owner-like field on Service.
        """
        field_names = [f.name for f in Service._meta.get_fields()]
        self.assertNotIn("owner", field_names)
