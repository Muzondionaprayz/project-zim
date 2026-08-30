from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.marketplace.models import MarketplaceListing


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class MyListingCreateTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.url = reverse("marketplace:my-listing-list")
        self.payload = {"title": "New Item", "city": "Harare", "province": "Harare"}

    def test_unauthenticated_cannot_create(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_can_create(self):
        self.authenticate_as(self.seller)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_seller_is_request_user(self):
        self.authenticate_as(self.seller)
        response = self.client.post(self.url, self.payload)
        listing = MarketplaceListing.objects.get(id=response.data["id"])
        self.assertEqual(listing.seller, self.seller)

    def test_client_cannot_spoof_seller(self):
        self.authenticate_as(self.seller)
        payload = {**self.payload, "seller": self.other_user.id}
        response = self.client.post(self.url, payload)
        listing = MarketplaceListing.objects.get(id=response.data["id"])
        self.assertEqual(listing.seller, self.seller)
        self.assertNotEqual(listing.seller, self.other_user)

    def test_defaults_to_draft_and_pending(self):
        self.authenticate_as(self.seller)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.data["status"], MarketplaceListing.Status.DRAFT)
        self.assertEqual(
            response.data["moderation_status"], MarketplaceListing.ModerationStatus.PENDING
        )

    def test_client_cannot_set_status_or_moderation_at_creation(self):
        self.authenticate_as(self.seller)
        payload = {
            **self.payload,
            "status": "published",
            "moderation_status": "approved",
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.data["status"], MarketplaceListing.Status.DRAFT)
        self.assertEqual(
            response.data["moderation_status"], MarketplaceListing.ModerationStatus.PENDING
        )

    def test_response_never_contains_seller_field(self):
        self.authenticate_as(self.seller)
        response = self.client.post(self.url, self.payload)
        self.assertNotIn("seller", response.data)


class MyListingListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.own = MarketplaceListing.objects.create(seller=self.seller, title="Mine")
        self.others = MarketplaceListing.objects.create(seller=self.other_user, title="Theirs")
        self.url = reverse("marketplace:my-listing-list")

    def test_list_only_returns_own(self):
        self.authenticate_as(self.seller)
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Mine"])

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyListingDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.listing = MarketplaceListing.objects.create(seller=self.seller, title="Mine")
        self.others_listing = MarketplaceListing.objects.create(
            seller=self.other_user, title="Theirs"
        )

    def test_owner_can_view(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.listing.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.listing.pk})
        response = self.client.patch(url, {"description": "Updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.description, "Updated")

    def test_cannot_view_others_listing(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.others_listing.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_modify_others_listing(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.others_listing.pk})
        response = self.client.patch(url, {"description": "Hacked"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_listing.refresh_from_db()
        self.assertNotEqual(self.others_listing.description, "Hacked")

    def test_cannot_delete_others_listing(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.others_listing.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MarketplaceListing.objects.filter(pk=self.others_listing.pk).exists())

    def test_owner_can_delete_own(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.listing.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_change_status_via_update(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.listing.pk})
        response = self.client.patch(url, {"status": "published"})
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, MarketplaceListing.Status.DRAFT)

    def test_cannot_change_moderation_status_via_update(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.listing.pk})
        response = self.client.patch(url, {"moderation_status": "approved"})
        self.listing.refresh_from_db()
        self.assertEqual(
            self.listing.moderation_status, MarketplaceListing.ModerationStatus.PENDING
        )

    def test_unauthenticated_cannot_view(self):
        url = reverse("marketplace:my-listing-detail", kwargs={"pk": self.listing.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PublishUnpublishAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.approved_listing = MarketplaceListing.objects.create(
            seller=self.seller,
            title="Approved",
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        self.pending_listing = MarketplaceListing.objects.create(
            seller=self.seller, title="Pending"
        )

    def test_owner_can_publish_approved_listing(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-publish", kwargs={"pk": self.approved_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.approved_listing.refresh_from_db()
        self.assertEqual(self.approved_listing.status, MarketplaceListing.Status.PUBLISHED)

    def test_cannot_publish_unapproved_listing(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:my-listing-publish", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_user_cannot_publish_someone_elses_listing(self):
        self.authenticate_as(self.other_user)
        url = reverse("marketplace:my-listing-publish", kwargs={"pk": self.approved_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_unpublish_published_listing(self):
        self.approved_listing.status = MarketplaceListing.Status.PUBLISHED
        self.approved_listing.save()
        self.authenticate_as(self.seller)
        url = reverse(
            "marketplace:my-listing-unpublish", kwargs={"pk": self.approved_listing.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.approved_listing.refresh_from_db()
        self.assertEqual(self.approved_listing.status, MarketplaceListing.Status.UNPUBLISHED)

    def test_other_user_cannot_unpublish_someone_elses_listing(self):
        self.approved_listing.status = MarketplaceListing.Status.PUBLISHED
        self.approved_listing.save()
        self.authenticate_as(self.other_user)
        url = reverse(
            "marketplace:my-listing-unpublish", kwargs={"pk": self.approved_listing.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_publish(self):
        url = reverse("marketplace:my-listing-publish", kwargs={"pk": self.approved_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
