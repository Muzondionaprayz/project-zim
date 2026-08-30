from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.businesses.models import Business, BusinessCategory
from apps.services.models import Service, ServiceCategory


class PublicServiceListTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.approved_business = Business.objects.create(
            owner=self.owner,
            name="Approved Biz",
            status=Business.Status.APPROVED,
            city="Harare",
            province="Harare",
        )
        self.draft_business = Business.objects.create(
            owner=self.owner, name="Draft Biz", status=Business.Status.DRAFT
        )
        self.category = ServiceCategory.objects.create(name="Catering")

        self.visible_service = Service.objects.create(
            business=self.approved_business,
            title="Visible Service",
            is_active=True,
            category=self.category,
        )
        self.inactive_service_on_approved_business = Service.objects.create(
            business=self.approved_business, title="Inactive Service", is_active=False
        )
        self.active_service_on_draft_business = Service.objects.create(
            business=self.draft_business, title="Draft Business Service", is_active=True
        )
        self.url = reverse("services:public-list")

    def test_list_is_accessible_without_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_contains_active_services_on_approved_businesses(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Service"])

    def test_list_excludes_inactive_service_even_on_approved_business(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertNotIn("Inactive Service", titles)

    def test_list_excludes_active_service_on_non_approved_business(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertNotIn("Draft Business Service", titles)

    def test_list_response_excludes_sensitive_business_fields(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertIn("business", item)
        self.assertNotIn("owner", item["business"])
        self.assertNotIn("verification_notes", item["business"])
        self.assertNotIn("is_active", item)  # internal publish flag not exposed

    def test_filter_by_business(self):
        other_business = Business.objects.create(
            owner=self.owner, name="Other Approved Biz", status=Business.Status.APPROVED
        )
        Service.objects.create(business=other_business, title="Other Service", is_active=True)
        response = self.client.get(self.url, {"business": self.approved_business.id})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Service"])

    def test_filter_by_category(self):
        Service.objects.create(
            business=self.approved_business, title="Uncategorized Service", is_active=True
        )
        response = self.client.get(self.url, {"category": self.category.slug})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Service"])

    def test_filter_by_city_via_business(self):
        bulawayo_business = Business.objects.create(
            owner=self.owner,
            name="Bulawayo Biz",
            status=Business.Status.APPROVED,
            city="Bulawayo",
        )
        Service.objects.create(
            business=bulawayo_business, title="Bulawayo Service", is_active=True
        )
        response = self.client.get(self.url, {"city": "Harare"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Service"])

    def test_search_by_title(self):
        response = self.client.get(self.url, {"search": "Visible"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Service"])


class PublicServiceDetailTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.approved_business = Business.objects.create(
            owner=self.owner, name="Approved Biz", status=Business.Status.APPROVED
        )
        self.draft_business = Business.objects.create(
            owner=self.owner, name="Draft Biz", status=Business.Status.DRAFT
        )
        self.visible_service = Service.objects.create(
            business=self.approved_business, title="Visible Service", is_active=True
        )
        self.inactive_service = Service.objects.create(
            business=self.approved_business, title="Inactive Service", is_active=False
        )
        self.service_on_draft_business = Service.objects.create(
            business=self.draft_business, title="Draft Business Service", is_active=True
        )

    def test_detail_accessible_without_authentication(self):
        url = reverse("services:public-detail", kwargs={"pk": self.visible_service.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detail_excludes_sensitive_fields(self):
        url = reverse("services:public-detail", kwargs={"pk": self.visible_service.pk})
        response = self.client.get(url)
        self.assertNotIn("is_active", response.data)
        self.assertNotIn("owner", response.data["business"])
        self.assertNotIn("verification_notes", response.data["business"])

    def test_inactive_service_detail_returns_404(self):
        url = reverse("services:public-detail", kwargs={"pk": self.inactive_service.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_service_on_non_approved_business_returns_404(self):
        url = reverse(
            "services:public-detail", kwargs={"pk": self.service_on_draft_business.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_service_returns_404(self):
        url = reverse("services:public-detail", kwargs={"pk": 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ServiceCategoryListTests(APITestCase):
    def test_category_list_is_public(self):
        ServiceCategory.objects.create(name="Catering")
        url = reverse("services:category-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_inactive_categories_are_excluded(self):
        ServiceCategory.objects.create(name="Active Cat", is_active=True)
        ServiceCategory.objects.create(name="Inactive Cat", is_active=False)
        url = reverse("services:category-list")
        response = self.client.get(url)
        names = [item["name"] for item in response.data]
        self.assertEqual(names, ["Active Cat"])
