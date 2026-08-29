from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class MeEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="me@example.com", password="a-strong-passw0rd!", first_name="Me"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.url = reverse("accounts:me")

    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_me_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_own_account(self):
        self.authenticate_as(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")

    def test_me_includes_profile(self):
        self.authenticate_as(self.user)
        response = self.client.get(self.url)
        self.assertIn("profile", response.data)

    def test_me_never_returns_password(self):
        self.authenticate_as(self.user)
        response = self.client.get(self.url)
        self.assertNotIn("password", response.data)

    def test_me_can_update_own_first_name(self):
        self.authenticate_as(self.user)
        response = self.client.patch(self.url, {"first_name": "Updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_me_can_update_own_profile_fields(self):
        self.authenticate_as(self.user)
        response = self.client.patch(
            self.url, {"profile": {"bio": "Hello world", "location": "Harare"}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Hello world")
        self.assertEqual(self.user.profile.location, "Harare")

    def test_me_cannot_change_own_role(self):
        self.authenticate_as(self.user)
        response = self.client.patch(self.url, {"role": "admin"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.CLIENT)

    def test_me_cannot_change_own_email(self):
        self.authenticate_as(self.user)
        response = self.client.patch(self.url, {"email": "hijacked@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@example.com")

    def test_me_only_returns_the_authenticated_users_own_data_not_others(self):
        self.authenticate_as(self.user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.data["email"], self.other_user.email)

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_auth_header_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="not-even-bearer-format")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
