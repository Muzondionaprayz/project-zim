from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.marketplace.models import ListingImage, MarketplaceListing
from apps.marketplace.permissions import IsListingImageOwner, IsListingOwner


class IsListingOwnerPermissionTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        self.permission = IsListingOwner()

    def test_allows_seller(self):
        request = Mock(user=self.seller)
        self.assertTrue(self.permission.has_object_permission(request, None, self.listing))

    def test_denies_non_seller(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.listing))


class IsListingImageOwnerPermissionTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        self.image = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/a.jpg"
        )
        self.permission = IsListingImageOwner()

    def test_allows_listing_owner(self):
        request = Mock(user=self.seller)
        self.assertTrue(self.permission.has_object_permission(request, None, self.image))

    def test_denies_non_owner(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.image))
