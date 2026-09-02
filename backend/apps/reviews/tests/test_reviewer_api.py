from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.marketplace.models import MarketplaceListing
from apps.reviews.models import Review
from apps.services.models import Service


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class CreateReviewAPITests(AuthenticatedAPITestCase):
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
        self.url = reverse("reviews:my-review-list")

    def test_unauthenticated_cannot_create_review(self):
        response = self.client.post(self.url, {"business": self.business.id, "rating": 5})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_review_business(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(
            self.url, {"business": self.business.id, "rating": 5, "body": "Nice"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_authenticated_user_can_review_service(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"service": self.service.id, "rating": 4})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_authenticated_user_can_review_listing(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(
            self.url, {"marketplace_listing": self.listing.id, "rating": 3}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reviewer_is_derived_from_request_user(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"business": self.business.id, "rating": 5})
        review = Review.objects.get(id=response.data["id"])
        self.assertEqual(review.reviewer, self.reviewer)

    def test_client_cannot_spoof_reviewer_field(self):
        """
        There is no writable "reviewer" field at all — even if
        supplied, the review must be attributed to request.user,
        never to the spoofed ID.
        """
        self.authenticate_as(self.reviewer)
        response = self.client.post(
            self.url, {"business": self.business.id, "rating": 5, "reviewer": self.owner.id}
        )
        review = Review.objects.get(id=response.data["id"])
        self.assertEqual(review.reviewer, self.reviewer)
        self.assertNotEqual(review.reviewer, self.owner)

    def test_client_cannot_spoof_status_at_creation(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(
            self.url, {"business": self.business.id, "rating": 5, "status": "hidden"}
        )
        self.assertEqual(response.data["status"], Review.Status.PUBLISHED)

    def test_no_target_returns_400(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"rating": 5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiple_targets_returns_400(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(
            self.url,
            {"business": self.business.id, "service": self.service.id, "rating": 5},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_business_returns_400_not_500(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"business": 999999, "rating": 5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_review_unapproved_business(self):
        draft_business = Business.objects.create(owner=self.owner, name="Draft Biz")
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"business": draft_business.id, "rating": 5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_cannot_review_own_business(self):
        self.authenticate_as(self.owner)
        response = self.client.post(self.url, {"business": self.business.id, "rating": 5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_submit_duplicate_review(self):
        self.authenticate_as(self.reviewer)
        first = self.client.post(self.url, {"business": self.business.id, "rating": 5})
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(self.url, {"business": self.business.id, "rating": 1})
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.filter(reviewer=self.reviewer).count(), 1)

    def test_rating_out_of_range_returns_400(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"business": self.business.id, "rating": 10})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_body_too_long_returns_400(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(
            self.url, {"business": self.business.id, "rating": 5, "body": "x" * 2001}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_rating_returns_400(self):
        self.authenticate_as(self.reviewer)
        response = self.client.post(self.url, {"business": self.business.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MyReviewListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.other_reviewer = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.own_review = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5
        )
        self.others_review = Review.objects.create(
            reviewer=self.other_reviewer, business=self.business, rating=1
        )
        self.url = reverse("reviews:my-review-list")

    def test_list_only_returns_own_reviews(self):
        self.authenticate_as(self.reviewer)
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.own_review.id])

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyReviewDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.other_reviewer = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.own_review = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5
        )
        self.others_review = Review.objects.create(
            reviewer=self.other_reviewer, business=self.business, rating=1
        )

    def test_owner_can_view_own_review(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.own_review.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update_own_review(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.own_review.pk})
        response = self.client.patch(url, {"rating": 3, "body": "Updated my mind"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_review.refresh_from_db()
        self.assertEqual(self.own_review.rating, 3)

    def test_cannot_view_another_users_review_via_my_endpoint(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.others_review.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_modify_another_users_review(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.others_review.pk})
        response = self.client.patch(url, {"rating": 1, "body": "Hacked"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_review.refresh_from_db()
        self.assertNotEqual(self.others_review.body, "Hacked")

    def test_cannot_delete_another_users_review(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.others_review.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Review.objects.filter(pk=self.others_review.pk).exists())

    def test_owner_can_delete_own_review(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.own_review.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Review.objects.filter(pk=self.own_review.pk).exists())

    def test_cannot_change_target_via_update(self):
        other_business = Business.objects.create(
            owner=self.owner, name="Other Biz", status=Business.Status.APPROVED
        )
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.own_review.pk})
        response = self.client.patch(url, {"business": other_business.id})
        self.own_review.refresh_from_db()
        self.assertEqual(self.own_review.business, self.business)

    def test_cannot_change_status_via_update(self):
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.own_review.pk})
        response = self.client.patch(url, {"status": "hidden"})
        self.own_review.refresh_from_db()
        self.assertEqual(self.own_review.status, Review.Status.PUBLISHED)

    def test_unauthenticated_cannot_view(self):
        url = reverse("reviews:my-review-detail", kwargs={"pk": self.own_review.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
