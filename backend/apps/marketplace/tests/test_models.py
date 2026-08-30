from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.marketplace.models import ListingImage, MarketplaceCategory, MarketplaceListing


class MarketplaceCategoryModelTests(TestCase):
    def test_slug_is_auto_generated(self):
        category = MarketplaceCategory.objects.create(name="Electronics & Gadgets")
        self.assertEqual(category.slug, "electronics-gadgets")

    def test_str_returns_name(self):
        category = MarketplaceCategory.objects.create(name="Furniture")
        self.assertEqual(str(category), "Furniture")


class MarketplaceListingModelTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )

    def test_defaults(self):
        listing = MarketplaceListing.objects.create(seller=self.seller, title="Sofa")
        self.assertEqual(listing.status, MarketplaceListing.Status.DRAFT)
        self.assertEqual(
            listing.moderation_status, MarketplaceListing.ModerationStatus.PENDING
        )

    def test_slug_auto_generated_and_unique(self):
        first = MarketplaceListing.objects.create(seller=self.seller, title="Chair")
        second = MarketplaceListing.objects.create(seller=self.seller, title="Chair")
        self.assertNotEqual(first.slug, second.slug)

    def test_deleting_seller_deletes_listing(self):
        listing = MarketplaceListing.objects.create(seller=self.seller, title="Doomed")
        listing_id = listing.id
        self.seller.delete()
        self.assertFalse(MarketplaceListing.objects.filter(id=listing_id).exists())

    def test_deleting_category_sets_null(self):
        category = MarketplaceCategory.objects.create(name="Cat")
        listing = MarketplaceListing.objects.create(
            seller=self.seller, title="Item", category=category
        )
        category.delete()
        listing.refresh_from_db()
        self.assertIsNone(listing.category)

    def test_negative_price_fails_validation(self):
        listing = MarketplaceListing(
            seller=self.seller, title="Bad Price", price=Decimal("-1")
        )
        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_is_publicly_visible_requires_published_and_approved(self):
        listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        self.assertFalse(listing.is_publicly_visible)

        listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
        listing.save()
        self.assertFalse(listing.is_publicly_visible)  # still draft status

        listing.status = MarketplaceListing.Status.PUBLISHED
        listing.save()
        self.assertTrue(listing.is_publicly_visible)

    def test_str_returns_title(self):
        listing = MarketplaceListing.objects.create(seller=self.seller, title="Title Item")
        self.assertEqual(str(listing), "Title Item")


class ListingImageModelTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")

    def test_deleting_listing_deletes_images(self):
        image = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/a.jpg"
        )
        image_id = image.id
        self.listing.delete()
        self.assertFalse(ListingImage.objects.filter(id=image_id).exists())

    def test_default_ordering_by_order_field(self):
        second = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/b.jpg", order=2
        )
        first = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/a.jpg", order=1
        )
        images = list(self.listing.images.all())
        self.assertEqual(images, [first, second])

    def test_str_representation(self):
        image = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/a.jpg", order=0
        )
        self.assertIn(str(self.listing.id), str(image))
