from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.reviews.models import Review
from apps.reviews.permissions import IsReviewOwner


class IsReviewOwnerPermissionTests(TestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.review = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5
        )
        self.permission = IsReviewOwner()

    def test_allows_reviewer(self):
        request = Mock(user=self.reviewer)
        self.assertTrue(self.permission.has_object_permission(request, None, self.review))

    def test_denies_non_reviewer(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.review))

    def test_denies_target_owner_who_is_not_the_reviewer(self):
        request = Mock(user=self.owner)
        self.assertFalse(self.permission.has_object_permission(request, None, self.review))
