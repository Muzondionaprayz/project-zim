from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.businesses.models import Business, BusinessCategory


class PublicBusinessListTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.category = BusinessCategory.objects.create(name="Catering")
        self.approved = Business.objects.create(
            owner=self.owner,
            name="Approved Biz",
            status=Business.Status.APPROVED,
            city="Harare",
            province="Harare",
            category=self.category,
        )
        self.draft = Business.objects.create(
            owner=self.owner, name="Draft Biz", status=Business.Status.DRAFT
        )
        self.pending = Business.objects.create(
            owner=self.owner, name="Pending Biz", status=Business.Status.PENDING
        )
        self.rejected = Business.objects.create(
            owner=self.owner, name="Rejected Biz", status=Business.Status.REJECTED
        )
        self.suspended = Business.objects.create(
            owner=self.owner, name="Suspended Biz", status=Business.Status.SUSPENDED
        )
        self.changes_requested = Business.objects.create(
            owner=self.owner,
            name="Changes Requested Biz",
            status=Business.Status.CHANGES_REQUESTED,
        )
        self.url = reverse("businesses:public-list")

    def test_list_is_accessible_without_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_contains_approved_businesses(self):
        response = self.client.get(self.url)
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Approved Biz"])

    def test_list_excludes_draft_pending_rejected_suspended_changes_requested(self):
        response = self.client.get(self.url)
        names = [item["name"] for item in response.data["results"]]
        for hidden_name in [
            "Draft Biz",
            "Pending Biz",
            "Rejected Biz",
            "Suspended Biz",
            "Changes Requested Biz",
        ]:
            self.assertNotIn(hidden_name, names)

    def test_list_response_excludes_sensitive_fields(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertNotIn("owner", item)
        self.assertNotIn("verification_notes", item)
        self.assertNotIn("email", item)  # excluded from the lightweight list serializer

    def test_filter_by_category_slug(self):
        other_category = BusinessCategory.objects.create(name="Salon")
        Business.objects.create(
            owner=self.owner,
            name="Salon Biz",
            status=Business.Status.APPROVED,
            category=other_category,
        )
        response = self.client.get(self.url, {"category": self.category.slug})
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Approved Biz"])

    def test_filter_by_city(self):
        Business.objects.create(
            owner=self.owner,
            name="Bulawayo Biz",
            status=Business.Status.APPROVED,
            city="Bulawayo",
        )
        response = self.client.get(self.url, {"city": "Harare"})
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Approved Biz"])

    def test_search_by_name(self):
        response = self.client.get(self.url, {"search": "Approved"})
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Approved Biz"])

    def test_search_with_no_match_returns_empty(self):
        response = self.client.get(self.url, {"search": "Nonexistent"})
        self.assertEqual(response.data["results"], [])


class PublicBusinessDetailTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.approved = Business.objects.create(
            owner=self.owner,
            name="Approved Biz",
            status=Business.Status.APPROVED,
            email="contact@approvedbiz.com",
        )
        self.draft = Business.objects.create(
            owner=self.owner, name="Draft Biz", status=Business.Status.DRAFT
        )

    def test_detail_accessible_without_authentication(self):
        url = reverse("businesses:public-detail", kwargs={"pk": self.approved.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detail_of_approved_business_returns_expected_fields(self):
        url = reverse("businesses:public-detail", kwargs={"pk": self.approved.pk})
        response = self.client.get(url)
        self.assertEqual(response.data["name"], "Approved Biz")
        self.assertEqual(response.data["email"], "contact@approvedbiz.com")

    def test_detail_excludes_sensitive_administrative_fields(self):
        url = reverse("businesses:public-detail", kwargs={"pk": self.approved.pk})
        response = self.client.get(url)
        self.assertNotIn("owner", response.data)
        self.assertNotIn("verification_notes", response.data)
        self.assertNotIn("submitted_at", response.data)
        self.assertNotIn("verified_at", response.data)

    def test_draft_business_detail_returns_404(self):
        url = reverse("businesses:public-detail", kwargs={"pk": self.draft.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_business_returns_404(self):
        url = reverse("businesses:public-detail", kwargs={"pk": 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BusinessCategoryListTests(APITestCase):
    def test_category_list_is_public(self):
        BusinessCategory.objects.create(name="Catering")
        url = reverse("businesses:category-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_inactive_categories_are_excluded(self):
        BusinessCategory.objects.create(name="Active Cat", is_active=True)
        BusinessCategory.objects.create(name="Inactive Cat", is_active=False)
        url = reverse("businesses:category-list")
        response = self.client.get(url)
        names = [item["name"] for item in response.data]
        self.assertEqual(names, ["Active Cat"])
