from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.jobs.models import Job


class NearbyLocationOnlyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.harare_biz = Business.objects.create(
            owner=self.user,
            name="Harare Biz",
            status=Business.Status.APPROVED,
            city="Harare",
            province="Harare",
        )
        self.bulawayo_biz = Business.objects.create(
            owner=self.user,
            name="Bulawayo Biz",
            status=Business.Status.APPROVED,
            city="Bulawayo",
            province="Bulawayo",
        )
        self.url = reverse("search:nearby")

    def test_nearby_is_public(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nearby_with_no_params_returns_all_visible(self):
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(titles, {"Harare Biz", "Bulawayo Biz"})

    def test_nearby_filters_by_city(self):
        response = self.client.get(self.url, {"city": "Harare"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Harare Biz"])

    def test_nearby_filters_by_province(self):
        response = self.client.get(self.url, {"province": "Bulawayo"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Bulawayo Biz"])


class NearbyRadiusSearchTests(APITestCase):
    """
    Harare coordinates ~ (-17.8252, 31.0335); Bulawayo ~ (-20.15, 28.5833).
    Great-circle distance between them is roughly 440km, used to
    build a radius search that includes one and excludes the other.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.harare_biz = Business.objects.create(
            owner=self.user,
            name="Harare Biz",
            status=Business.Status.APPROVED,
            city="Harare",
            latitude=Decimal("-17.825200"),
            longitude=Decimal("31.033500"),
        )
        self.bulawayo_biz = Business.objects.create(
            owner=self.user,
            name="Bulawayo Biz",
            status=Business.Status.APPROVED,
            city="Bulawayo",
            latitude=Decimal("-20.150000"),
            longitude=Decimal("28.583300"),
        )
        self.no_coords_biz = Business.objects.create(
            owner=self.user, name="No Coords Biz", status=Business.Status.APPROVED
        )
        self.url = reverse("search:nearby")

    def test_small_radius_around_harare_excludes_bulawayo(self):
        response = self.client.get(
            self.url,
            {
                "latitude": "-17.8252",
                "longitude": "31.0335",
                "radius_km": "50",
                "types": "businesses",
            },
        )
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Harare Biz"])

    def test_large_radius_includes_both(self):
        response = self.client.get(
            self.url,
            {
                "latitude": "-17.8252",
                "longitude": "31.0335",
                "radius_km": "600",
                "types": "businesses",
            },
        )
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(titles, {"Harare Biz", "Bulawayo Biz"})

    def test_radius_search_excludes_business_without_coordinates(self):
        response = self.client.get(
            self.url,
            {
                "latitude": "-17.8252",
                "longitude": "31.0335",
                "radius_km": "10000",
                "types": "businesses",
            },
        )
        titles = {item["title"] for item in response.data["results"]}
        self.assertNotIn("No Coords Biz", titles)

    def test_result_includes_distance_km(self):
        response = self.client.get(
            self.url,
            {
                "latitude": "-17.8252",
                "longitude": "31.0335",
                "radius_km": "50",
                "types": "businesses",
            },
        )
        item = response.data["results"][0]
        self.assertIn("distance_km", item)
        self.assertLess(item["distance_km"], 1)  # essentially the same point

    def test_closest_result_first(self):
        response = self.client.get(
            self.url,
            {
                "latitude": "-17.8252",
                "longitude": "31.0335",
                "radius_km": "600",
                "types": "businesses",
            },
        )
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles[0], "Harare Biz")

    def test_partial_coordinates_returns_400(self):
        response = self.client.get(self.url, {"latitude": "-17.8", "longitude": "31.0"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_radius_returns_400(self):
        response = self.client.get(
            self.url, {"latitude": "-17.8", "longitude": "31.0", "radius_km": "0"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_latitude_out_of_range_returns_400(self):
        response = self.client.get(
            self.url, {"latitude": "200", "longitude": "31.0", "radius_km": "10"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_longitude_out_of_range_returns_400(self):
        response = self.client.get(
            self.url, {"latitude": "-17.8", "longitude": "300", "radius_km": "10"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_numeric_radius_returns_400(self):
        response = self.client.get(
            self.url, {"latitude": "-17.8", "longitude": "31.0", "radius_km": "far"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_radius_search_with_other_types_falls_back_to_location_filters(self):
        Job.objects.create(
            employer=self.user, title="Harare Job", status=Job.Status.OPEN, city="Harare"
        )
        response = self.client.get(
            self.url,
            {
                "latitude": "-17.8252",
                "longitude": "31.0335",
                "radius_km": "50",
                "types": "businesses,jobs",
                "city": "Harare",
            },
        )
        titles = {item["title"] for item in response.data["results"]}
        self.assertIn("Harare Job", titles)
        self.assertIn("Harare Biz", titles)
