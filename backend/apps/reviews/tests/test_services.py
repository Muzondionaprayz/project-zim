from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.marketplace.models import MarketplaceListing
from apps.reviews import services
from apps.reviews.models import Review
from apps.services.models import Service


class CreateReviewServiceTests(TestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.unapproved_business = Business.objects.create(owner=self.owner, name="Draft Biz")
        self.service = Service.objects.create(
            business=self.business, title="Svc", is_active=True
        )
        self.listing = MarketplaceListing.objects.create(
            seller=self.owner,
            title="Item",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )

    def test_create_review_for_business_succeeds(self):
        review = services.create_review(
            self.reviewer, business=self.business, rating=5, body="Great!"
        )
        self.assertEqual(review.business, self.business)
        self.assertEqual(review.reviewer, self.reviewer)

    def test_create_review_for_service_succeeds(self):
        review = services.create_review(self.reviewer, service=self.service, rating=4)
        self.assertEqual(review.service, self.service)

    def test_create_review_for_listing_succeeds(self):
        review = services.create_review(
            self.reviewer, marketplace_listing=self.listing, rating=3
        )
        self.assertEqual(review.marketplace_listing, self.listing)

    def test_no_target_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.create_review(self.reviewer, rating=5)

    def test_multiple_targets_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.create_review(
                self.reviewer, business=self.business, service=self.service, rating=5
            )

    def test_cannot_review_unapproved_business(self):
        with self.assertRaises(ValidationError):
            services.create_review(self.reviewer, business=self.unapproved_business, rating=5)

    def test_cannot_review_inactive_service(self):
        inactive_service = Service.objects.create(
            business=self.business, title="Inactive Svc", is_active=False
        )
        with self.assertRaises(ValidationError):
            services.create_review(self.reviewer, service=inactive_service, rating=5)

    def test_cannot_review_unapproved_listing(self):
        pending_listing = MarketplaceListing.objects.create(seller=self.owner, title="Pending")
        with self.assertRaises(ValidationError):
            services.create_review(
                self.reviewer, marketplace_listing=pending_listing, rating=5
            )

    def test_owner_cannot_review_own_business(self):
        with self.assertRaises(ValidationError):
            services.create_review(self.owner, business=self.business, rating=5)

    def test_business_owner_cannot_review_own_service(self):
        with self.assertRaises(ValidationError):
            services.create_review(self.owner, service=self.service, rating=5)

    def test_seller_cannot_review_own_listing(self):
        with self.assertRaises(ValidationError):
            services.create_review(self.owner, marketplace_listing=self.listing, rating=5)

    def test_duplicate_review_is_rejected(self):
        services.create_review(self.reviewer, business=self.business, rating=5)
        with self.assertRaises(ValidationError):
            services.create_review(self.reviewer, business=self.business, rating=1)

    def test_review_created_with_default_status_published(self):
        review = services.create_review(self.reviewer, business=self.business, rating=5)
        self.assertEqual(review.status, Review.Status.PUBLISHED)


class ModerationServiceTests(TestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.review = services.create_review(self.reviewer, business=self.business, rating=1)

    def test_hide_published_review_succeeds(self):
        services.hide_review(self.review, notes="Abusive content")
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.Status.HIDDEN)
        self.assertEqual(self.review.moderation_notes, "Abusive content")

    def test_hide_already_hidden_review_is_rejected(self):
        services.hide_review(self.review)
        with self.assertRaises(ValidationError):
            services.hide_review(self.review)

    def test_restore_hidden_review_succeeds(self):
        services.hide_review(self.review)
        services.restore_review(self.review)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.Status.PUBLISHED)

    def test_restore_published_review_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.restore_review(self.review)
