from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.marketplace import services
from apps.marketplace.models import ListingImage, MarketplaceListing


class PublishUnpublishServiceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )

    def test_publish_approved_draft_succeeds(self):
        listing = MarketplaceListing.objects.create(
            seller=self.seller,
            title="Item",
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        services.publish_listing(listing)
        listing.refresh_from_db()
        self.assertEqual(listing.status, MarketplaceListing.Status.PUBLISHED)

    def test_publish_unapproved_listing_is_rejected(self):
        listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        with self.assertRaises(ValidationError):
            services.publish_listing(listing)

    def test_publish_already_published_is_rejected(self):
        listing = MarketplaceListing.objects.create(
            seller=self.seller,
            title="Item",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        with self.assertRaises(ValidationError):
            services.publish_listing(listing)

    def test_unpublish_published_listing_succeeds(self):
        listing = MarketplaceListing.objects.create(
            seller=self.seller,
            title="Item",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        services.unpublish_listing(listing)
        listing.refresh_from_db()
        self.assertEqual(listing.status, MarketplaceListing.Status.UNPUBLISHED)

    def test_unpublish_draft_listing_is_rejected(self):
        listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        with self.assertRaises(ValidationError):
            services.unpublish_listing(listing)


class ModerationServiceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )

    def _pending(self):
        return MarketplaceListing.objects.create(seller=self.seller, title="Item")

    def test_approve_pending_succeeds(self):
        listing = self._pending()
        services.approve_listing(listing, notes="ok")
        listing.refresh_from_db()
        self.assertEqual(listing.moderation_status, MarketplaceListing.ModerationStatus.APPROVED)
        self.assertEqual(listing.moderation_notes, "ok")

    def test_approve_non_pending_is_rejected(self):
        listing = self._pending()
        listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
        listing.save()
        with self.assertRaises(ValidationError):
            services.approve_listing(listing)

    def test_reject_pending_succeeds(self):
        listing = self._pending()
        services.reject_listing(listing, notes="no")
        listing.refresh_from_db()
        self.assertEqual(listing.moderation_status, MarketplaceListing.ModerationStatus.REJECTED)

    def test_request_changes_pending_succeeds(self):
        listing = self._pending()
        services.request_listing_changes(listing, notes="fix photos")
        listing.refresh_from_db()
        self.assertEqual(
            listing.moderation_status, MarketplaceListing.ModerationStatus.CHANGES_REQUESTED
        )

    def test_suspend_approved_succeeds(self):
        listing = self._pending()
        listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
        listing.save()
        services.suspend_listing(listing, notes="complaint")
        listing.refresh_from_db()
        self.assertEqual(listing.moderation_status, MarketplaceListing.ModerationStatus.SUSPENDED)

    def test_suspend_pending_is_rejected(self):
        listing = self._pending()
        with self.assertRaises(ValidationError):
            services.suspend_listing(listing)

    def test_restore_suspended_succeeds(self):
        listing = self._pending()
        listing.moderation_status = MarketplaceListing.ModerationStatus.SUSPENDED
        listing.save()
        services.restore_listing(listing)
        listing.refresh_from_db()
        self.assertEqual(listing.moderation_status, MarketplaceListing.ModerationStatus.APPROVED)

    def test_restore_pending_is_rejected(self):
        listing = self._pending()
        with self.assertRaises(ValidationError):
            services.restore_listing(listing)


class ListingImageServiceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")

    def test_first_image_is_primary_by_default(self):
        image = services.add_listing_image(self.listing, "https://example.com/a.jpg")
        self.assertTrue(image.is_primary)

    def test_second_image_is_not_primary_by_default(self):
        services.add_listing_image(self.listing, "https://example.com/a.jpg")
        second = services.add_listing_image(self.listing, "https://example.com/b.jpg")
        self.assertFalse(second.is_primary)

    def test_cannot_exceed_ten_images(self):
        for i in range(10):
            services.add_listing_image(self.listing, f"https://example.com/{i}.jpg")
        with self.assertRaises(ValidationError):
            services.add_listing_image(self.listing, "https://example.com/eleventh.jpg")
        self.assertEqual(self.listing.images.count(), 10)

    def test_set_primary_image_demotes_previous_primary(self):
        first = services.add_listing_image(self.listing, "https://example.com/a.jpg")
        second = services.add_listing_image(self.listing, "https://example.com/b.jpg")
        self.assertTrue(first.is_primary)
        self.assertFalse(second.is_primary)

        services.set_primary_image(second)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)

    def test_at_most_one_primary_image_per_listing(self):
        first = services.add_listing_image(self.listing, "https://example.com/a.jpg")
        second = services.add_listing_image(self.listing, "https://example.com/b.jpg")
        services.set_primary_image(second)
        primary_count = ListingImage.objects.filter(
            listing=self.listing, is_primary=True
        ).count()
        self.assertEqual(primary_count, 1)
