from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business, BusinessCategory


class BusinessCategoryModelTests(TestCase):
    def test_slug_is_auto_generated_from_name(self):
        category = BusinessCategory.objects.create(name="Plumbing & Repairs")
        self.assertEqual(category.slug, "plumbing-repairs")

    def test_explicit_slug_is_preserved(self):
        category = BusinessCategory.objects.create(name="Salon", slug="beauty-salon")
        self.assertEqual(category.slug, "beauty-salon")

    def test_str_returns_name(self):
        category = BusinessCategory.objects.create(name="Catering")
        self.assertEqual(str(category), "Catering")


class BusinessModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.category = BusinessCategory.objects.create(name="Catering")

    def test_business_defaults_to_draft_status(self):
        business = Business.objects.create(owner=self.owner, name="Jane's Catering")
        self.assertEqual(business.status, Business.Status.DRAFT)

    def test_slug_is_auto_generated_from_name(self):
        business = Business.objects.create(owner=self.owner, name="Jane's Catering")
        self.assertTrue(business.slug.startswith("janes-catering"))

    def test_duplicate_names_get_unique_slugs(self):
        first = Business.objects.create(owner=self.owner, name="Best Bakery")
        second_owner = User.objects.create_user(
            email="owner2@example.com", password="a-strong-passw0rd!"
        )
        second = Business.objects.create(owner=second_owner, name="Best Bakery")
        self.assertNotEqual(first.slug, second.slug)

    def test_is_publicly_visible_only_when_approved(self):
        business = Business.objects.create(owner=self.owner, name="Hidden Biz")
        self.assertFalse(business.is_publicly_visible)
        business.status = Business.Status.APPROVED
        business.save()
        self.assertTrue(business.is_publicly_visible)

    def test_deleting_category_sets_null_not_cascade(self):
        business = Business.objects.create(
            owner=self.owner, name="Cat Biz", category=self.category
        )
        self.category.delete()
        business.refresh_from_db()
        self.assertIsNone(business.category)

    def test_deleting_owner_deletes_business(self):
        business = Business.objects.create(owner=self.owner, name="Owned Biz")
        business_id = business.id
        self.owner.delete()
        self.assertFalse(Business.objects.filter(id=business_id).exists())

    def test_latitude_out_of_range_fails_validation(self):
        business = Business(owner=self.owner, name="Bad Lat", latitude=Decimal("120.0"))
        with self.assertRaises(ValidationError):
            business.full_clean()

    def test_longitude_out_of_range_fails_validation(self):
        business = Business(owner=self.owner, name="Bad Long", longitude=Decimal("200.0"))
        with self.assertRaises(ValidationError):
            business.full_clean()

    def test_valid_latitude_longitude_passes_validation(self):
        business = Business(
            owner=self.owner,
            name="Good Coords",
            latitude=Decimal("-17.824858"),
            longitude=Decimal("31.053028"),
        )
        business.full_clean()  # should not raise

    def test_valid_opening_hours_passes_validation(self):
        business = Business(
            owner=self.owner,
            name="Open Hours Biz",
            opening_hours={
                "monday": {"open": "08:00", "close": "17:00"},
                "sunday": None,
            },
        )
        business.full_clean()  # should not raise

    def test_invalid_opening_hours_day_fails_validation(self):
        business = Business(
            owner=self.owner,
            name="Bad Day Biz",
            opening_hours={"funday": {"open": "08:00", "close": "17:00"}},
        )
        with self.assertRaises(ValidationError):
            business.full_clean()

    def test_invalid_opening_hours_shape_fails_validation(self):
        business = Business(
            owner=self.owner,
            name="Bad Shape Biz",
            opening_hours={"monday": "all day"},
        )
        with self.assertRaises(ValidationError):
            business.full_clean()

    def test_str_returns_name(self):
        business = Business.objects.create(owner=self.owner, name="String Biz")
        self.assertEqual(str(business), "String Biz")
