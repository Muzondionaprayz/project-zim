from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.services.models import Service


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class MyServiceCreateTests(AuthenticatedAPITestCase):
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
        self.url = reverse("services:my-service-list")

    def test_unauthenticated_user_cannot_create_service(self):
        response = self.client.post(
            self.url, {"business": self.own_business.id, "title": "New Service"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Service.objects.filter(title="New Service").exists())

    def test_authenticated_user_can_create_service_under_own_business(self):
        self.authenticate_as(self.owner)
        response = self.client.post(
            self.url, {"business": self.own_business.id, "title": "New Service"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        service = Service.objects.get(id=response.data["id"])
        self.assertEqual(service.business, self.own_business)

    def test_user_cannot_create_service_under_another_users_business(self):
        """
        The core Phase 4 security requirement: a client must not be
        able to create a service under a business it doesn't own,
        even by supplying that business's real, valid ID.
        """
        self.authenticate_as(self.owner)
        response = self.client.post(
            self.url, {"business": self.others_business.id, "title": "Sneaky Service"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("business", response.data)
        self.assertFalse(Service.objects.filter(title="Sneaky Service").exists())

    def test_created_service_defaults_to_active(self):
        self.authenticate_as(self.owner)
        response = self.client.post(
            self.url, {"business": self.own_business.id, "title": "New Service"}
        )
        self.assertTrue(response.data["is_active"])

    def test_client_cannot_set_is_active_false_at_creation(self):
        """is_active is read-only; publish state is controlled only via activate/deactivate."""
        self.authenticate_as(self.owner)
        response = self.client.post(
            self.url,
            {
                "business": self.own_business.id,
                "title": "New Service",
                "is_active": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_active"])

    def test_missing_business_is_rejected(self):
        self.authenticate_as(self.owner)
        response = self.client.post(self.url, {"title": "No Business Service"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("business", response.data)


class MyServiceListTests(AuthenticatedAPITestCase):
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
        self.own_service = Service.objects.create(business=self.own_business, title="My Svc")
        self.others_service = Service.objects.create(
            business=self.others_business, title="Their Svc"
        )
        self.url = reverse("services:my-service-list")

    def test_list_only_returns_services_under_own_businesses(self):
        self.authenticate_as(self.owner)
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["My Svc"])
        self.assertNotIn("Their Svc", titles)

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyServiceDetailTests(AuthenticatedAPITestCase):
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
        self.own_service = Service.objects.create(business=self.own_business, title="My Svc")
        self.others_service = Service.objects.create(
            business=self.others_business, title="Their Svc"
        )

    def test_owner_can_view_own_service(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.own_service.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update_own_service(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.own_service.pk})
        response = self.client.patch(url, {"description": "Updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_service.refresh_from_db()
        self.assertEqual(self.own_service.description, "Updated")

    def test_user_cannot_view_another_users_service(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.others_service.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_modify_another_users_service(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.others_service.pk})
        response = self.client.patch(url, {"description": "Hacked!"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_service.refresh_from_db()
        self.assertNotEqual(self.others_service.description, "Hacked!")

    def test_user_cannot_delete_another_users_service(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.others_service.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Service.objects.filter(pk=self.others_service.pk).exists())

    def test_owner_can_delete_own_service(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.own_service.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Service.objects.filter(pk=self.own_service.pk).exists())

    def test_owner_cannot_move_service_to_another_users_business(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.own_service.pk})
        response = self.client.patch(url, {"business": self.others_business.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.own_service.refresh_from_db()
        self.assertEqual(self.own_service.business, self.own_business)

    def test_owner_cannot_change_is_active_via_update(self):
        self.authenticate_as(self.owner)
        url = reverse("services:my-service-detail", kwargs={"pk": self.own_service.pk})
        response = self.client.patch(url, {"is_active": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_service.refresh_from_db()
        self.assertTrue(self.own_service.is_active)  # unchanged; is_active is read-only

    def test_unauthenticated_user_cannot_view_service_detail(self):
        url = reverse("services:my-service-detail", kwargs={"pk": self.own_service.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ActivateDeactivateServiceAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.approved_business = Business.objects.create(
            owner=self.owner, name="Approved Biz", status=Business.Status.APPROVED
        )
        self.draft_business = Business.objects.create(owner=self.owner, name="Draft Biz")
        self.service_on_approved = Service.objects.create(
            business=self.approved_business, title="Svc", is_active=False
        )
        self.service_on_draft = Service.objects.create(
            business=self.draft_business, title="Draft Biz Svc", is_active=False
        )

    def test_owner_can_activate_service_on_approved_business(self):
        self.authenticate_as(self.owner)
        url = reverse(
            "services:my-service-activate", kwargs={"pk": self.service_on_approved.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service_on_approved.refresh_from_db()
        self.assertTrue(self.service_on_approved.is_active)

    def test_activate_service_on_non_approved_business_is_rejected(self):
        self.authenticate_as(self.owner)
        url = reverse(
            "services:my-service-activate", kwargs={"pk": self.service_on_draft.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.service_on_draft.refresh_from_db()
        self.assertFalse(self.service_on_draft.is_active)

    def test_user_cannot_activate_another_users_service(self):
        self.authenticate_as(self.other_user)
        url = reverse(
            "services:my-service-activate", kwargs={"pk": self.service_on_approved.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_deactivate_service(self):
        self.service_on_approved.is_active = True
        self.service_on_approved.save()
        self.authenticate_as(self.owner)
        url = reverse(
            "services:my-service-deactivate", kwargs={"pk": self.service_on_approved.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service_on_approved.refresh_from_db()
        self.assertFalse(self.service_on_approved.is_active)

    def test_user_cannot_deactivate_another_users_service(self):
        self.service_on_approved.is_active = True
        self.service_on_approved.save()
        self.authenticate_as(self.other_user)
        url = reverse(
            "services:my-service-deactivate", kwargs={"pk": self.service_on_approved.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_activate(self):
        url = reverse(
            "services:my-service-activate", kwargs={"pk": self.service_on_approved.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
