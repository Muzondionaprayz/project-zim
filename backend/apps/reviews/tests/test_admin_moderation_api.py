from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.reviews.models import Review


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class ReviewModerationActionTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.review = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=1, body="Terrible"
        )

    def test_admin_can_hide_review(self):
        self.authenticate_as(self.admin)
        url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        response = self.client.post(url, {"notes": "Abusive language"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.Status.HIDDEN)

    def test_ordinary_user_cannot_hide_review(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.Status.PUBLISHED)

    def test_review_author_cannot_hide_own_review(self):
        """Review authors are not granted moderation powers over their own content."""
        self.authenticate_as(self.reviewer)
        url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_business_owner_cannot_hide_review_of_their_own_business(self):
        """Owning the reviewed business does not grant moderation powers either."""
        self.authenticate_as(self.owner)
        url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_hide_review(self):
        url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_restore_hidden_review(self):
        self.review.status = Review.Status.HIDDEN
        self.review.save()
        self.authenticate_as(self.admin)
        url = reverse("reviews:admin-restore", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.Status.PUBLISHED)

    def test_ordinary_user_cannot_restore_review(self):
        self.review.status = Review.Status.HIDDEN
        self.review.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("reviews:admin-restore", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_transition_returns_400_not_500(self):
        """Hiding an already-hidden review is a bad request, not a server error."""
        self.review.status = Review.Status.HIDDEN
        self.review.save()
        self.authenticate_as(self.admin)
        url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hidden_review_excluded_from_public_list_after_moderation(self):
        self.authenticate_as(self.admin)
        hide_url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        self.client.post(hide_url)

        self.client.credentials()  # clear auth for the public request
        public_url = reverse("reviews:public-list")
        response = self.client.get(public_url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.review.id, ids)

    def test_moderation_notes_never_exposed_publicly(self):
        self.authenticate_as(self.admin)
        hide_url = reverse("reviews:admin-hide", kwargs={"pk": self.review.pk})
        self.client.post(hide_url, {"notes": "Contains internal detail"})

        restore_url = reverse("reviews:admin-restore", kwargs={"pk": self.review.pk})
        self.client.post(restore_url)

        self.client.credentials()
        public_url = reverse("reviews:public-detail", kwargs={"pk": self.review.pk})
        response = self.client.get(public_url)
        self.assertNotIn("moderation_notes", response.data)
