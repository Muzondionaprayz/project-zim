from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class AdminUserListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="client@example.com", password="a-strong-passw0rd!"
        )
        self.url = reverse("adminpanel:user-list")

    def test_admin_can_list_users(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ordinary_user_cannot_list_users(self):
        self.authenticate_as(self.client_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_list_users(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_role(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"role": "admin"})
        emails = [item["email"] for item in response.data["results"]]
        self.assertEqual(emails, ["admin@example.com"])

    def test_filter_by_search(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"search": "client"})
        emails = [item["email"] for item in response.data["results"]]
        self.assertEqual(emails, ["client@example.com"])

    def test_list_never_exposes_password(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        for item in response.data["results"]:
            self.assertNotIn("password", item)


class AdminUserDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="client@example.com", password="a-strong-passw0rd!"
        )

    def test_admin_can_view_any_user_detail(self):
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-detail", kwargs={"pk": self.client_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ordinary_user_cannot_view_user_detail(self):
        self.authenticate_as(self.client_user)
        url = reverse("adminpanel:user-detail", kwargs={"pk": self.admin.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_view_user_detail(self):
        url = reverse("adminpanel:user-detail", kwargs={"pk": self.client_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminChangeUserRoleAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="client@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )

    def test_admin_can_change_another_users_role(self):
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-change-role", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url, {"role": "provider"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, User.Role.PROVIDER)

    def test_ordinary_user_cannot_change_roles(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("adminpanel:user-change-role", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url, {"role": "admin"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, User.Role.CLIENT)

    def test_admin_cannot_change_own_role_self_demotion_guard(self):
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-change-role", kwargs={"pk": self.admin.pk})
        response = self.client.post(url, {"role": "client"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_invalid_role_value_returns_400(self):
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-change-role", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url, {"role": "superuser"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_change_role(self):
        url = reverse("adminpanel:user-change-role", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url, {"role": "provider"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_cannot_use_this_endpoint_to_self_promote(self):
        """
        A non-admin cannot use this endpoint at all — it's blocked by
        IsAdminRole before the target/role is even inspected, so
        there is no path for a client to grant themselves admin.
        """
        self.authenticate_as(self.ordinary_user)
        url = reverse("adminpanel:user-change-role", kwargs={"pk": self.ordinary_user.pk})
        response = self.client.post(url, {"role": "admin"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.ordinary_user.refresh_from_db()
        self.assertEqual(self.ordinary_user.role, User.Role.CLIENT)


class AdminActivateDeactivateUserAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="client@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )

    def test_admin_can_deactivate_another_user(self):
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-deactivate", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)

    def test_admin_cannot_deactivate_own_account_self_lockout_guard(self):
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-deactivate", kwargs={"pk": self.admin.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_ordinary_user_cannot_deactivate_anyone(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("adminpanel:user-deactivate", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_reactivate_deactivated_user(self):
        self.client_user.is_active = False
        self.client_user.save()
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-activate", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_active)

    def test_ordinary_user_cannot_activate_anyone(self):
        self.client_user.is_active = False
        self.client_user.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("adminpanel:user-activate", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivated_user_cannot_log_in(self):
        """
        Confirms the deactivation actually has teeth: an existing
        Phase 2 guarantee (inactive users are rejected at login),
        exercised here through the new admin deactivate action.
        """
        self.authenticate_as(self.admin)
        url = reverse("adminpanel:user-deactivate", kwargs={"pk": self.client_user.pk})
        self.client.post(url)

        self.client.credentials()
        login_url = reverse("accounts:login")
        response = self.client.post(
            login_url, {"email": "client@example.com", "password": "a-strong-passw0rd!"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_deactivate(self):
        url = reverse("adminpanel:user-deactivate", kwargs={"pk": self.client_user.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
