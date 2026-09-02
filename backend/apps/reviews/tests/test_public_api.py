from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.reviews.models import Review


class PublicReviewListTests(APITestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!", first_name="Jane"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.other_business = Business.objects.create(
            owner=self.owner, name="Other Biz", status=Business.Status.APPROVED
        )
        self.published = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5, body="Great!"
        )
        self.hidden = Review.objects.create(
            reviewer=self.reviewer,
            business=self.other_business,
            rating=1,
            status=Review.Status.HIDDEN,
        )
        self.url = reverse("reviews:public-list")

    def test_list_accessible_without_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_contains_published_reviews(self):
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.published.id])

    def test_hidden_review_excluded_from_list(self):
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.hidden.id, ids)

    def test_filter_by_business(self):
        response = self.client.get(self.url, {"business": self.business.id})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.published.id])

    def test_filter_by_business_excludes_other_business_reviews(self):
        third_reviewer = User.objects.create_user(
            email="third@example.com", password="a-strong-passw0rd!"
        )
        another_published = Review.objects.create(
            reviewer=third_reviewer, business=self.other_business, rating=4
        )
        response = self.client.get(self.url, {"business": self.business.id})
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(another_published.id, ids)

    def test_list_reviewer_shows_only_first_name_no_email(self):
        response = self.client.get(self.url)
        reviewer_data = response.data["results"][0]["reviewer"]
        self.assertEqual(reviewer_data["first_name"], "Jane")
        self.assertNotIn("email", reviewer_data)

    def test_list_excludes_moderation_and_status_fields(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertNotIn("status", item)
        self.assertNotIn("moderation_notes", item)

    def test_list_excludes_target_fk_fields(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertNotIn("business", item)
        self.assertNotIn("service", item)
        self.assertNotIn("marketplace_listing", item)


class PublicReviewDetailTests(APITestCase):
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
        self.other_business = Business.objects.create(
            owner=self.owner, name="Other Biz", status=Business.Status.APPROVED
        )
        self.published = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5
        )
        self.hidden = Review.objects.create(
            reviewer=self.reviewer, business=self.other_business, rating=1, status=Review.Status.HIDDEN
        )

    def test_published_review_detail_accessible(self):
        url = reverse("reviews:public-detail", kwargs={"pk": self.published.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hidden_review_detail_returns_404(self):
        url = reverse("reviews:public-detail", kwargs={"pk": self.hidden.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_review_returns_404(self):
        url = reverse("reviews:public-detail", kwargs={"pk": 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
