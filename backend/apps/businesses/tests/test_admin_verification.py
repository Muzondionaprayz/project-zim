from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.businesses.models import Business


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class AdminVerificationActionTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="a-strong-passw0rd!",
            role=User.Role.ADMIN,
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.pending_business = Business.objects.create(
            owner=self.owner, name="Pending Biz", status=Business.Status.PENDING
        )

    def test_admin_can_approve_pending_business(self):
        self.authenticate_as(self.admin)
        url = reverse("businesses:admin-approve", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url, {"notes": "All good"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_business.refresh_from_db()
        self.assertEqual(self.pending_business.status, Business.Status.APPROVED)

    def test_ordinary_user_cannot_approve_business(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("businesses:admin-approve", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.pending_business.refresh_from_db()
        self.assertEqual(self.pending_business.status, Business.Status.PENDING)

    def test_business_owner_cannot_approve_their_own_business(self):
        """Owning a business does not grant admin verification powers over it."""
        self.authenticate_as(self.owner)
        url = reverse("businesses:admin-approve", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_approve_business(self):
        url = reverse("businesses:admin-approve", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_reject_pending_business(self):
        self.authenticate_as(self.admin)
        url = reverse("businesses:admin-reject", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url, {"notes": "Incomplete details"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_business.refresh_from_db()
        self.assertEqual(self.pending_business.status, Business.Status.REJECTED)

    def test_ordinary_user_cannot_reject_business(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("businesses:admin-reject", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_request_changes_on_pending_business(self):
        self.authenticate_as(self.admin)
        url = reverse(
            "businesses:admin-request-changes", kwargs={"pk": self.pending_business.pk}
        )
        response = self.client.post(url, {"notes": "Add opening hours"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_business.refresh_from_db()
        self.assertEqual(self.pending_business.status, Business.Status.CHANGES_REQUESTED)

    def test_ordinary_user_cannot_request_changes(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse(
            "businesses:admin-request-changes", kwargs={"pk": self.pending_business.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_suspend_approved_business(self):
        self.pending_business.status = Business.Status.APPROVED
        self.pending_business.save()
        self.authenticate_as(self.admin)
        url = reverse("businesses:admin-suspend", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url, {"notes": "Complaint received"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_business.refresh_from_db()
        self.assertEqual(self.pending_business.status, Business.Status.SUSPENDED)

    def test_ordinary_user_cannot_suspend_business(self):
        self.pending_business.status = Business.Status.APPROVED
        self.pending_business.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("businesses:admin-suspend", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_restore_suspended_business(self):
        self.pending_business.status = Business.Status.SUSPENDED
        self.pending_business.save()
        self.authenticate_as(self.admin)
        url = reverse("businesses:admin-restore", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_business.refresh_from_db()
        self.assertEqual(self.pending_business.status, Business.Status.APPROVED)

    def test_ordinary_user_cannot_restore_business(self):
        self.pending_business.status = Business.Status.SUSPENDED
        self.pending_business.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("businesses:admin-restore", kwargs={"pk": self.pending_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_transition_returns_400_not_500(self):
        """Approving a draft (not pending) business is a bad request, not a server error."""
        draft_business = Business.objects.create(owner=self.owner, name="Draft Biz")
        self.authenticate_as(self.admin)
        url = reverse("businesses:admin-approve", kwargs={"pk": draft_business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
