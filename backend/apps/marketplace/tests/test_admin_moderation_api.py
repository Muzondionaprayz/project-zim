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


class AdminModerationActionTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.pending_listing = MarketplaceListing.objects.create(
            seller=self.seller, title="Pending Item"
        )

    def test_admin_can_approve(self):
        self.authenticate_as(self.admin)
        url = reverse("marketplace:admin-approve", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url, {"notes": "Looks good"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_listing.refresh_from_db()
        self.assertEqual(
            self.pending_listing.moderation_status, MarketplaceListing.ModerationStatus.APPROVED
        )

    def test_ordinary_user_cannot_approve(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("marketplace:admin-approve", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_cannot_approve_own_listing(self):
        self.authenticate_as(self.seller)
        url = reverse("marketplace:admin-approve", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_approve(self):
        url = reverse("marketplace:admin-approve", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_reject(self):
        self.authenticate_as(self.admin)
        url = reverse("marketplace:admin-reject", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url, {"notes": "Not allowed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_listing.refresh_from_db()
        self.assertEqual(
            self.pending_listing.moderation_status, MarketplaceListing.ModerationStatus.REJECTED
        )

    def test_ordinary_user_cannot_reject(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("marketplace:admin-reject", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_request_changes(self):
        self.authenticate_as(self.admin)
        url = reverse(
            "marketplace:admin-request-changes", kwargs={"pk": self.pending_listing.pk}
        )
        response = self.client.post(url, {"notes": "Add more photos"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_listing.refresh_from_db()
        self.assertEqual(
            self.pending_listing.moderation_status,
            MarketplaceListing.ModerationStatus.CHANGES_REQUESTED,
        )

    def test_ordinary_user_cannot_request_changes(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse(
            "marketplace:admin-request-changes", kwargs={"pk": self.pending_listing.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_suspend_approved_listing(self):
        self.pending_listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
        self.pending_listing.save()
        self.authenticate_as(self.admin)
        url = reverse("marketplace:admin-suspend", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url, {"notes": "Complaint"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_listing.refresh_from_db()
        self.assertEqual(
            self.pending_listing.moderation_status, MarketplaceListing.ModerationStatus.SUSPENDED
        )

    def test_ordinary_user_cannot_suspend(self):
        self.pending_listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
        self.pending_listing.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("marketplace:admin-suspend", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_restore_suspended_listing(self):
        self.pending_listing.moderation_status = MarketplaceListing.ModerationStatus.SUSPENDED
        self.pending_listing.save()
        self.authenticate_as(self.admin)
        url = reverse("marketplace:admin-restore", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_listing.refresh_from_db()
        self.assertEqual(
            self.pending_listing.moderation_status, MarketplaceListing.ModerationStatus.APPROVED
        )

    def test_ordinary_user_cannot_restore(self):
        self.pending_listing.moderation_status = MarketplaceListing.ModerationStatus.SUSPENDED
        self.pending_listing.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("marketplace:admin-restore", kwargs={"pk": self.pending_listing.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_transition_returns_400_not_500(self):
        approved = MarketplaceListing.objects.create(
            seller=self.seller,
            title="Already Approved",
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        self.authenticate_as(self.admin)
        url = reverse("marketplace:admin-approve", kwargs={"pk": approved.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
