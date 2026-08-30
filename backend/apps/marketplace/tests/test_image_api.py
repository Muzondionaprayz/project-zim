from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.marketplace.models import ListingImage, MarketplaceListing


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class ListingImageCreateTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        self.others_listing = MarketplaceListing.objects.create(
            seller=self.other_user, title="Their Item"
        )
        self.url = reverse("marketplace:my-image-list")

    def test_unauthenticated_cannot_add_image(self):
        response = self.client.post(
            self.url, {"listing": self.listing.id, "image_url": "https://example.com/a.jpg"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_add_image_to_own_listing(self):
        self.authenticate_as(self.seller)
        response = self.client.post(
            self.url, {"listing": self.listing.id, "image_url": "https://example.com/a.jpg"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_add_image_to_another_users_listing(self):
        """
        The core security requirement: a client must not be able to
        attach an image to a listing it doesn't own, even by
        supplying that listing's real, valid ID.
        """
        self.authenticate_as(self.seller)
        response = self.client.post(
            self.url,
            {"listing": self.others_listing.id, "image_url": "https://example.com/a.jpg"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("listing", response.data)

    def test_first_image_becomes_primary(self):
        self.authenticate_as(self.seller)
        response = self.client.post(
            self.url, {"listing": self.listing.id, "image_url": "https://example.com/a.jpg"}
        )
        self.assertTrue(response.data["is_primary"])

    def test_client_cannot_force_is_primary_on_second_image(self):
        self.authenticate_as(self.seller)
        self.client.post(
            self.url, {"listing": self.listing.id, "image_url": "https://example.com/a.jpg"}
        )
        response = self.client.post(
            self.url,
            {
                "listing": self.listing.id,
                "image_url": "https://example.com/b.jpg",
                "is_primary": True,
            },
        )
        self.assertFalse(response.data["is_primary"])

    def test_eleventh_image_is_rejected(self):
        self.authenticate_as(self.seller)
        for i in range(10):
            response = self.client.post(
                self.url,
                {"listing": self.listing.id, "image_url": f"https://example.com/{i}.jpg"},
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            self.url,
            {"listing": self.listing.id, "image_url": "https://example.com/eleventh.jpg"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.listing.images.count(), 10)


class ListingImageDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        self.others_listing = MarketplaceListing.objects.create(
            seller=self.other_user, title="Their Item"
        )
        self.image = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/a.jpg", is_primary=True
        )
        self.others_image = ListingImage.objects.create(
            listing=self.others_listing, image_url="https://example.com/b.jpg", is_primary=True
        )

    def test_owner_can_view_own_image(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-image-detail", kwargs={"pk": self.image.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_view_others_image(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-image-detail", kwargs={"pk": self.others_image.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_others_image(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-image-detail", kwargs={"pk": self.others_image.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ListingImage.objects.filter(pk=self.others_image.pk).exists())

    def test_owner_can_delete_own_image(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-image-detail", kwargs={"pk": self.image.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class SetPrimaryImageTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Item")
        self.first = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/a.jpg", is_primary=True
        )
        self.second = ListingImage.objects.create(
            listing=self.listing, image_url="https://example.com/b.jpg", is_primary=False
        )

    def test_owner_can_set_primary(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-image-set-primary", kwargs={"pk": self.second.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertFalse(self.first.is_primary)
        self.assertTrue(self.second.is_primary)

    def test_other_user_cannot_set_primary_on_someone_elses_image(self):
        self.authenticate_as(self.other_user)
        url = reverse("marketplace:my-image-set-primary", kwargs={"pk": self.second.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_set_primary(self):
        url = reverse("marketplace:my-image-set-primary", kwargs={"pk": self.second.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
