from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User


class LoginTests(APITestCase):
    def setUp(self):
        self.password = "a-strong-passw0rd!"
        self.user = User.objects.create_user(email="login@example.com", password=self.password)
        self.url = reverse("accounts:login")

    def test_login_with_correct_credentials_returns_tokens(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": self.password}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_response_includes_user_summary(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": self.password}
        )
        self.assertEqual(response.data["user"]["email"], "login@example.com")
        self.assertEqual(response.data["user"]["role"], User.Role.CLIENT)

    def test_login_with_wrong_password_is_rejected(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    def test_login_with_unknown_email_is_rejected(self):
        response = self.client.post(
            self.url, {"email": "ghost@example.com", "password": "whatever123"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": self.password}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshTests(APITestCase):
    def setUp(self):
        self.password = "a-strong-passw0rd!"
        self.user = User.objects.create_user(email="refresh@example.com", password=self.password)
        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": "refresh@example.com", "password": self.password},
        )
        self.refresh_token = login_response.data["refresh"]
        self.url = reverse("accounts:refresh")

    def test_refresh_returns_new_access_token(self):
        response = self.client.post(self.url, {"refresh": self.refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_with_invalid_token_is_rejected(self):
        response = self.client.post(self.url, {"refresh": "not-a-real-token"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_refresh_token(self):
        response = self.client.post(self.url, {"refresh": self.refresh_token})
        self.assertIn("refresh", response.data)
        self.assertNotEqual(response.data["refresh"], self.refresh_token)
