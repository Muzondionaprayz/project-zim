from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.marketplace.models import MarketplaceListing
from apps.reviews.models import Review
from apps.services.models import Service


class ReviewModelTests(TestCase):
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

    def test_defaults_to_published(self):
        review = Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        self.assertEqual(review.status, Review.Status.PUBLISHED)

    def test_is_publicly_visible_true_when_published(self):
        review = Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        self.assertTrue(review.is_publicly_visible)

    def test_is_publicly_visible_false_when_hidden(self):
        review = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5, status=Review.Status.HIDDEN
        )
        self.assertFalse(review.is_publicly_visible)

    def test_target_property_returns_business(self):
        review = Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        self.assertEqual(review.target, self.business)

    def test_rating_below_minimum_fails_validation(self):
        review = Review(reviewer=self.reviewer, business=self.business, rating=0)
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_rating_above_maximum_fails_validation(self):
        review = Review(reviewer=self.reviewer, business=self.business, rating=6)
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_valid_rating_boundaries_pass_validation(self):
        Review(reviewer=self.reviewer, business=self.business, rating=1).full_clean()
        Review(reviewer=self.reviewer, business=self.business, rating=5).full_clean()

    def test_body_over_max_length_fails_validation(self):
        review = Review(
            reviewer=self.reviewer, business=self.business, rating=5, body="x" * 2001
        )
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_deleting_business_deletes_review(self):
        review = Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        review_id = review.id
        self.business.delete()
        self.assertFalse(Review.objects.filter(id=review_id).exists())

    def test_deleting_reviewer_deletes_review(self):
        review = Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        review_id = review.id
        self.reviewer.delete()
        self.assertFalse(Review.objects.filter(id=review_id).exists())

    def test_str_representation(self):
        review = Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        self.assertIn(str(review.pk), str(review))


class ReviewDuplicatePreventionDBTests(TestCase):
    """
    Explicit DB-level duplicate-prevention tests: these bypass
    services.create_review entirely and hit Review.objects.create()
    directly, proving the constraint itself (not just the Python
    check in services.py) rejects duplicates.
    """

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
        self.service = Service.objects.create(
            business=self.business, title="Svc", is_active=True
        )
        self.listing = MarketplaceListing.objects.create(
            seller=self.owner,
            title="Item",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )

    def test_duplicate_business_review_rejected_at_db_level(self):
        Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(reviewer=self.reviewer, business=self.business, rating=3)

    def test_duplicate_service_review_rejected_at_db_level(self):
        Review.objects.create(reviewer=self.reviewer, service=self.service, rating=5)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(reviewer=self.reviewer, service=self.service, rating=3)

    def test_duplicate_listing_review_rejected_at_db_level(self):
        Review.objects.create(reviewer=self.reviewer, marketplace_listing=self.listing, rating=5)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(
                    reviewer=self.reviewer, marketplace_listing=self.listing, rating=3
                )

    def test_same_reviewer_can_review_different_target_types(self):
        """
        Confirms the partial-index design doesn't accidentally block
        a reviewer from reviewing a business AND a service AND a
        listing (the NULL-handling bug this design avoids would
        manifest as either false positives or false negatives here).
        """
        Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        Review.objects.create(reviewer=self.reviewer, service=self.service, rating=4)
        Review.objects.create(reviewer=self.reviewer, marketplace_listing=self.listing, rating=3)
        self.assertEqual(Review.objects.filter(reviewer=self.reviewer).count(), 3)

    def test_different_reviewers_can_review_same_business(self):
        other_reviewer = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        Review.objects.create(reviewer=self.reviewer, business=self.business, rating=5)
        Review.objects.create(reviewer=other_reviewer, business=self.business, rating=2)
        self.assertEqual(Review.objects.filter(business=self.business).count(), 2)
