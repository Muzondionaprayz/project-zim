from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.services.models import Service
from apps.services.permissions import IsServiceOwner


class IsServiceOwnerPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(owner=self.owner, name="Biz")
        self.service = Service.objects.create(business=self.business, title="Svc")
        self.permission = IsServiceOwner()

    def test_allows_business_owner(self):
        request = Mock(user=self.owner)
        self.assertTrue(self.permission.has_object_permission(request, None, self.service))

    def test_denies_non_owner(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.service))
