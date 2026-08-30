from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.marketplace.models import MarketplaceCategory, MarketplaceListing


def _published_approved(**kwargs):
    kwargs.setdefault("status", MarketplaceListing.Status.PUBLISHED)
    kwargs.setdefault("moderation_status", MarketplaceListing.ModerationStatus.APPROVED)
    return MarketplaceListing.objects.create(**kwargs)


class PublicListingListTests(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.category = MarketplaceCategory.objects.create(name="Electronics")

        self.visible = _published_approved(
            seller=self.seller, title="Visible Item", city="Harare",
            province="Harare", category=self.category,
        )
        self.draft = MarketplaceListing.objects.create(seller=self.seller, title="Draft Item")
        self.pending = MarketplaceListing.objects.create(
            seller=self.seller, title="Pending Item", status=MarketplaceListing.Status.PUBLISHED
        )
        self.rejected = _published_approved(
            seller=self.seller, title="Rejected but published (edge case)",
            moderation_status=MarketplaceListing.ModerationStatus.REJECTED,
        )
        self.suspended = _published_approved(
            seller=self.seller, title="Suspended Item",
            moderation_status=MarketplaceListing.ModerationStatus.SUSPENDED,
        )
        self.unpublished_approved = MarketplaceListing.objects.create(
            seller=self.seller, title="Unpublished Approved Item",
            status=MarketplaceListing.Status.UNPUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        self.url = reverse("marketplace:public-list")

    def test_list_accessible_without_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_contains_published_and_approved(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Item"])

    def test_list_excludes_all_other_states(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        for hidden in [
            "Draft Item", "Pending Item", "Rejected but published (edge case)",
            "Suspended Item", "Unpublished Approved Item",
        ]:
            self.assertNotIn(hidden, titles)

    def test_list_excludes_sensitive_fields(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertNotIn("seller", item)
        self.assertNotIn("moderation_status", item)
        self.assertNotIn("moderation_notes", item)

    def test_filter_by_category(self):
        _published_approved(seller=self.seller, title="Other Cat Item")
        response = self.client.get(self.url, {"category": self.category.slug})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Item"])

    def test_filter_by_city(self):
        _published_approved(seller=self.seller, title="Bulawayo Item", city="Bulawayo")
        response = self.client.get(self.url, {"city": "Harare"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Item"])

    def test_search_by_title(self):
        response = self.client.get(self.url, {"search": "Visible"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible Item"])


class PublicListingDetailTests(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.visible = _published_approved(
            seller=self.seller, title="Visible Item", email="contact@example.com"
        )
        self.draft = MarketplaceListing.objects.create(seller=self.seller, title="Draft Item")

    def test_detail_accessible_without_authentication(self):
        url = reverse("marketplace:public-detail", kwargs={"pk": self.visible.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detail_excludes_sensitive_fields(self):
        url = reverse("marketplace:public-detail", kwargs={"pk": self.visible.pk})
        response = self.client.get(url)
        self.assertNotIn("seller", response.data)
        self.assertNotIn("status", response.data)
        self.assertNotIn("moderation_status", response.data)
        self.assertNotIn("moderation_notes", response.data)

    def test_draft_listing_returns_404(self):
        url = reverse("marketplace:public-detail", kwargs={"pk": self.draft.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_listing_returns_404(self):
        url = reverse("marketplace:public-detail", kwargs={"pk": 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MarketplaceCategoryListTests(APITestCase):
    def test_category_list_is_public(self):
        MarketplaceCategory.objects.create(name="Electronics")
        url = reverse("marketplace:category-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_inactive_categories_excluded(self):
        MarketplaceCategory.objects.create(name="Active", is_active=True)
        MarketplaceCategory.objects.create(name="Inactive", is_active=False)
        url = reverse("marketplace:category-list")
        response = self.client.get(url)
        names = [item["name"] for item in response.data]
        self.assertEqual(names, ["Active"])
