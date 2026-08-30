from unittest.mock import Mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.businesses.permissions import IsBusinessOwner
from apps.businesses.validators import validate_opening_hours


class OpeningHoursValidatorTests(TestCase):
    def test_empty_dict_is_valid(self):
        validate_opening_hours({})  # should not raise

    def test_none_is_valid(self):
        validate_opening_hours(None)  # should not raise

    def test_valid_shape_passes(self):
        validate_opening_hours(
            {
                "monday": {"open": "08:00", "close": "17:00"},
                "sunday": None,
            }
        )  # should not raise

    def test_unknown_day_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_opening_hours({"someday": {"open": "08:00", "close": "17:00"}})

    def test_non_dict_top_level_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_opening_hours("always open")

    def test_non_dict_day_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_opening_hours({"monday": "9-5"})

    def test_unexpected_key_within_day_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_opening_hours({"monday": {"open": "08:00", "notes": "busy"}})

    def test_non_string_time_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_opening_hours({"monday": {"open": 800, "close": "17:00"}})


class IsBusinessOwnerPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(owner=self.owner, name="Biz")
        self.permission = IsBusinessOwner()

    def test_allows_owner(self):
        request = Mock(user=self.owner)
        self.assertTrue(self.permission.has_object_permission(request, None, self.business))

    def test_denies_non_owner(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.business))
