from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User


class RegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:register")
        self.payload = {
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "role": "client",
            "password": "a-strong-passw0rd!",
            "password_confirm": "a-strong-passw0rd!",
        }

    def test_register_creates_user(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_register_does_not_require_authentication(self):
        response = self.client.post(self.url, self.payload)
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_response_never_contains_password(self):
        response = self.client.post(self.url, self.payload)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_confirm", response.data)

    def test_register_rejects_mismatched_passwords(self):
        payload = {**self.payload, "password_confirm": "different-password!"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(email="newuser@example.com", password="whatever-pass1")
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_rejects_weak_password(self):
        payload = {**self.payload, "email": "weak@example.com", "password": "123", "password_confirm": "123"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_admin_role_self_assignment(self):
        payload = {**self.payload, "email": "wannabe-admin@example.com", "role": "admin"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
        self.assertFalse(User.objects.filter(email="wannabe-admin@example.com").exists())

    def test_register_allows_provider_role(self):
        payload = {**self.payload, "email": "provider@example.com", "role": "provider"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email="provider@example.com").role, "provider")

    def test_register_created_user_has_hashed_password(self):
        self.client.post(self.url, self.payload)
        user = User.objects.get(email="newuser@example.com")
        self.assertNotEqual(user.password, self.payload["password"])
        self.assertTrue(user.check_password(self.payload["password"]))
