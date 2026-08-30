from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.businesses.models import Business, BusinessCategory


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class MyBusinessCreateTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.url = reverse("businesses:my-business-list")
        self.payload = {"name": "My New Biz", "city": "Harare", "province": "Harare"}

    def test_unauthenticated_user_cannot_create_business(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Business.objects.filter(name="My New Biz").exists())

    def test_authenticated_user_can_create_business(self):
        self.authenticate_as(self.owner)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Business.objects.filter(name="My New Biz").exists())

    def test_created_business_owner_is_request_user(self):
        self.authenticate_as(self.owner)
        response = self.client.post(self.url, self.payload)
        business = Business.objects.get(id=response.data["id"])
        self.assertEqual(business.owner, self.owner)

    def test_client_cannot_spoof_ownership_via_owner_field(self):
        """
        Submitting another user's ID as "owner" must be silently
        ignored — the created business must still belong to the
        authenticated request.user, never to the spoofed ID.
        """
        self.authenticate_as(self.owner)
        payload = {**self.payload, "owner": self.other_user.id}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        business = Business.objects.get(id=response.data["id"])
        self.assertEqual(business.owner, self.owner)
        self.assertNotEqual(business.owner, self.other_user)

    def test_created_business_defaults_to_draft(self):
        self.authenticate_as(self.owner)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.data["status"], Business.Status.DRAFT)

    def test_client_cannot_set_status_at_creation(self):
        self.authenticate_as(self.owner)
        payload = {**self.payload, "status": "approved"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.data["status"], Business.Status.DRAFT)

    def test_response_never_contains_other_users_data(self):
        self.authenticate_as(self.owner)
        response = self.client.post(self.url, self.payload)
        self.assertNotIn("owner", response.data)


class MyBusinessListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.own_business = Business.objects.create(owner=self.owner, name="My Biz")
        self.others_business = Business.objects.create(
            owner=self.other_user, name="Their Biz"
        )
        self.url = reverse("businesses:my-business-list")

    def test_list_only_returns_own_businesses(self):
        self.authenticate_as(self.owner)
        response = self.client.get(self.url)
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["My Biz"])
        self.assertNotIn("Their Biz", names)

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyBusinessDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(owner=self.owner, name="My Biz")
        self.others_business = Business.objects.create(
            owner=self.other_user, name="Their Biz"
        )

    def test_owner_can_view_own_business(self):
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-detail", kwargs={"pk": self.business.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update_own_business(self):
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-detail", kwargs={"pk": self.business.pk})
        response = self.client.patch(url, {"description": "Updated description"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.business.refresh_from_db()
        self.assertEqual(self.business.description, "Updated description")

    def test_user_cannot_view_another_users_business(self):
        self.authenticate_as(self.owner)
        url = reverse(
            "businesses:my-business-detail", kwargs={"pk": self.others_business.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_modify_another_users_business(self):
        self.authenticate_as(self.owner)
        url = reverse(
            "businesses:my-business-detail", kwargs={"pk": self.others_business.pk}
        )
        response = self.client.patch(url, {"description": "Hacked!"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_business.refresh_from_db()
        self.assertNotEqual(self.others_business.description, "Hacked!")

    def test_user_cannot_delete_another_users_business(self):
        self.authenticate_as(self.owner)
        url = reverse(
            "businesses:my-business-detail", kwargs={"pk": self.others_business.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Business.objects.filter(pk=self.others_business.pk).exists())

    def test_owner_can_delete_own_business(self):
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-detail", kwargs={"pk": self.business.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Business.objects.filter(pk=self.business.pk).exists())

    def test_owner_cannot_change_own_business_status_via_update(self):
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-detail", kwargs={"pk": self.business.pk})
        response = self.client.patch(url, {"status": "approved"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Business.Status.DRAFT)

    def test_owner_cannot_change_own_business_owner_via_update(self):
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-detail", kwargs={"pk": self.business.pk})
        response = self.client.patch(url, {"owner": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.business.refresh_from_db()
        self.assertEqual(self.business.owner, self.owner)

    def test_unauthenticated_user_cannot_view_business_detail(self):
        url = reverse("businesses:my-business-detail", kwargs={"pk": self.business.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SubmitForVerificationAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(owner=self.owner, name="My Biz")

    def test_owner_can_submit_own_draft_business(self):
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-submit", kwargs={"pk": self.business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Business.Status.PENDING)

    def test_user_cannot_submit_another_users_business(self):
        self.authenticate_as(self.other_user)
        url = reverse("businesses:my-business-submit", kwargs={"pk": self.business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Business.Status.DRAFT)

    def test_submitting_already_pending_business_is_rejected(self):
        self.business.status = Business.Status.PENDING
        self.business.save()
        self.authenticate_as(self.owner)
        url = reverse("businesses:my-business-submit", kwargs={"pk": self.business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_user_cannot_submit(self):
        url = reverse("businesses:my-business-submit", kwargs={"pk": self.business.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
