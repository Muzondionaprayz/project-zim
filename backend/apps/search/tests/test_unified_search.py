from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.businesses.models import Business, BusinessCategory
from apps.jobs.models import Job
from apps.marketplace.models import MarketplaceListing
from apps.services.models import Service


class UnifiedSearchCrossDomainTests(APITestCase):
    """Confirms one visible record from each domain is returned, and hidden ones aren't."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.category = BusinessCategory.objects.create(name="Catering")

        # Visible business
        self.business = Business.objects.create(
            owner=self.user,
            name="Visible Biz",
            status=Business.Status.APPROVED,
            category=self.category,
            city="Harare",
            province="Harare",
        )
        # Hidden business (not approved)
        Business.objects.create(owner=self.user, name="Hidden Biz")

        # Visible service (active + business approved)
        self.service = Service.objects.create(
            business=self.business, title="Visible Service", is_active=True, price=50
        )
        # Hidden service: inactive
        Service.objects.create(business=self.business, title="Inactive Service", is_active=False)
        # Hidden service: business not approved
        other_biz = Business.objects.create(owner=self.user, name="Other Biz")
        Service.objects.create(business=other_biz, title="Orphan Service", is_active=True)

        # Visible job
        self.job = Job.objects.create(
            employer=self.user, title="Visible Job", status=Job.Status.OPEN, budget=100
        )
        # Hidden job: draft
        Job.objects.create(employer=self.user, title="Draft Job")
        # Hidden job: closed
        Job.objects.create(employer=self.user, title="Closed Job", status=Job.Status.CLOSED)

        # Visible marketplace listing
        self.listing = MarketplaceListing.objects.create(
            seller=self.user,
            title="Visible Listing",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
            price=75,
        )
        # Hidden: unapproved
        MarketplaceListing.objects.create(seller=self.user, title="Pending Listing")

        self.url = reverse("search:unified")

    def test_search_is_public(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_all_four_visible_records_are_returned(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(
            titles, {"Visible Biz", "Visible Service", "Visible Job", "Visible Listing"}
        )

    def test_hidden_business_excluded(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertNotIn("Hidden Biz", titles)

    def test_inactive_service_excluded(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertNotIn("Inactive Service", titles)

    def test_service_under_unapproved_business_excluded(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertNotIn("Orphan Service", titles)

    def test_draft_and_closed_jobs_excluded(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertNotIn("Draft Job", titles)
        self.assertNotIn("Closed Job", titles)

    def test_unapproved_marketplace_listing_excluded(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertNotIn("Pending Listing", titles)

    def test_entity_types_are_correctly_labeled(self):
        response = self.client.get(self.url)
        by_title = {item["title"]: item["entity_type"] for item in response.data["results"]}
        self.assertEqual(by_title["Visible Biz"], "business")
        self.assertEqual(by_title["Visible Service"], "service")
        self.assertEqual(by_title["Visible Job"], "job")
        self.assertEqual(by_title["Visible Listing"], "marketplace")

    def test_result_includes_detail_path(self):
        response = self.client.get(self.url)
        item = next(i for i in response.data["results"] if i["title"] == "Visible Biz")
        self.assertEqual(item["detail_path"], f"/api/v1/businesses/{self.business.pk}/")


class UnifiedSearchTextQueryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.matching = Business.objects.create(
            owner=self.user, name="Amazing Plumbing Co", status=Business.Status.APPROVED
        )
        self.non_matching = Business.objects.create(
            owner=self.user, name="Other Business", status=Business.Status.APPROVED
        )
        self.url = reverse("search:unified")

    def test_q_matches_title(self):
        response = self.client.get(self.url, {"q": "Plumbing"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Amazing Plumbing Co"])

    def test_q_matches_description(self):
        self.non_matching.description = "We do plumbing work too"
        self.non_matching.save()
        response = self.client.get(self.url, {"q": "plumbing"})
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(titles, {"Amazing Plumbing Co", "Other Business"})

    def test_q_with_no_matches_returns_empty(self):
        response = self.client.get(self.url, {"q": "Nonexistent Zebra Corp"})
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["count"], 0)


class UnifiedSearchTypeFilterTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        Business.objects.create(
            owner=self.user, name="A Business", status=Business.Status.APPROVED
        )
        Job.objects.create(employer=self.user, title="A Job", status=Job.Status.OPEN)
        self.url = reverse("search:unified")

    def test_types_filters_to_single_domain(self):
        response = self.client.get(self.url, {"types": "businesses"})
        entity_types = {item["entity_type"] for item in response.data["results"]}
        self.assertEqual(entity_types, {"business"})

    def test_types_filters_to_multiple_domains(self):
        response = self.client.get(self.url, {"types": "businesses,jobs"})
        entity_types = {item["entity_type"] for item in response.data["results"]}
        self.assertEqual(entity_types, {"business", "job"})

    def test_invalid_type_returns_400(self):
        response = self.client.get(self.url, {"types": "spaceships"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("types", response.data)

    def test_empty_types_param_means_all(self):
        response = self.client.get(self.url, {"types": ""})
        entity_types = {item["entity_type"] for item in response.data["results"]}
        self.assertEqual(entity_types, {"business", "job"})


class UnifiedSearchCategoryLocationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.cat_a = BusinessCategory.objects.create(name="Catering")
        self.cat_b = BusinessCategory.objects.create(name="Plumbing")
        self.harare_biz = Business.objects.create(
            owner=self.user,
            name="Harare Biz",
            status=Business.Status.APPROVED,
            category=self.cat_a,
            city="Harare",
            province="Harare",
            address="123 Samora Machel Ave",
        )
        self.bulawayo_biz = Business.objects.create(
            owner=self.user,
            name="Bulawayo Biz",
            status=Business.Status.APPROVED,
            category=self.cat_b,
            city="Bulawayo",
            province="Bulawayo",
        )
        self.url = reverse("search:unified")

    def test_category_filter(self):
        response = self.client.get(self.url, {"category": self.cat_a.slug})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Harare Biz"])

    def test_city_filter(self):
        response = self.client.get(self.url, {"city": "Harare"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Harare Biz"])

    def test_province_filter(self):
        response = self.client.get(self.url, {"province": "Bulawayo"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Bulawayo Biz"])

    def test_area_filter_matches_address(self):
        response = self.client.get(self.url, {"area": "Samora Machel"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Harare Biz"])


class UnifiedSearchPriceFilterTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.user, name="Biz", status=Business.Status.APPROVED
        )
        self.cheap = Service.objects.create(
            business=self.business, title="Cheap Service", is_active=True, price=10
        )
        self.expensive = Service.objects.create(
            business=self.business, title="Expensive Service", is_active=True, price=500
        )
        self.no_price_job = Job.objects.create(
            employer=self.user, title="No Price Job", status=Job.Status.OPEN
        )
        self.url = reverse("search:unified")

    def test_price_min_filters_out_cheaper_items(self):
        response = self.client.get(self.url, {"types": "services", "price_min": "100"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Expensive Service"])

    def test_price_max_filters_out_pricier_items(self):
        response = self.client.get(self.url, {"types": "services", "price_max": "100"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Cheap Service"])

    def test_price_range(self):
        response = self.client.get(
            self.url, {"types": "services", "price_min": "5", "price_max": "20"}
        )
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Cheap Service"])

    def test_null_price_excluded_when_price_min_given(self):
        response = self.client.get(self.url, {"types": "jobs", "price_min": "1"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertNotIn("No Price Job", titles)

    def test_invalid_price_returns_400(self):
        response = self.client.get(self.url, {"price_min": "not-a-number"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UnifiedSearchRatingAndVerifiedNoOpTests(APITestCase):
    """
    min_rating and is_verified must be safely accepted without error
    and without filtering anything out, since no rating system exists
    (see apps.search.services docstring).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        Business.objects.create(
            owner=self.user, name="Biz", status=Business.Status.APPROVED
        )
        self.url = reverse("search:unified")

    def test_min_rating_param_does_not_error_or_filter(self):
        response = self.client.get(self.url, {"min_rating": "4.5"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_is_verified_param_does_not_error_or_filter(self):
        response = self.client.get(self.url, {"is_verified": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_rating_field_is_always_null_in_results(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.data["results"][0]["rating"])


class UnifiedSearchPaginationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        for i in range(25):
            Business.objects.create(
                owner=self.user, name=f"Biz {i}", status=Business.Status.APPROVED
            )
        self.url = reverse("search:unified")

    def test_default_page_size_is_paginated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 25)
        self.assertLess(len(response.data["results"]), 25)

    def test_page_param_returns_next_page(self):
        first_page = self.client.get(self.url)
        second_page = self.client.get(self.url, {"page": 2})
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        first_ids = {item["id"] for item in first_page.data["results"]}
        second_ids = {item["id"] for item in second_page.data["results"]}
        self.assertEqual(first_ids.isdisjoint(second_ids), True)

    def test_invalid_page_returns_404(self):
        response = self.client.get(self.url, {"page": "9999"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UnifiedSearchSensitiveFieldTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        Business.objects.create(
            owner=self.user,
            name="Biz",
            status=Business.Status.APPROVED,
            verification_notes="internal notes",
        )
        MarketplaceListing.objects.create(
            seller=self.user,
            title="Listing",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
            moderation_notes="internal moderation notes",
        )
        self.url = reverse("search:unified")

    def test_no_result_exposes_owner_or_seller_identity(self):
        response = self.client.get(self.url)
        for item in response.data["results"]:
            self.assertNotIn("owner", item)
            self.assertNotIn("seller", item)
            self.assertNotIn("employer", item)

    def test_no_result_exposes_moderation_or_verification_fields(self):
        response = self.client.get(self.url)
        for item in response.data["results"]:
            self.assertNotIn("moderation_notes", item)
            self.assertNotIn("verification_notes", item)
            self.assertNotIn("status", item)
            self.assertNotIn("moderation_status", item)

    def test_no_result_exposes_email_or_phone(self):
        response = self.client.get(self.url)
        for item in response.data["results"]:
            self.assertNotIn("email", item)
            self.assertNotIn("phone", item)
            self.assertNotIn("whatsapp", item)
