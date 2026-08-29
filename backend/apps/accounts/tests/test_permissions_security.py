from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.permissions import IsAdminRole, IsSelf


class IsSelfPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="self@example.com", password="pass-word-123!")
        self.other = User.objects.create_user(email="other@example.com", password="pass-word-123!")
        self.permission = IsSelf()

    def test_allows_access_to_own_object(self):
        request = Mock(user=self.user)
        self.assertTrue(self.permission.has_object_permission(request, None, self.user))

    def test_denies_access_to_another_users_object(self):
        request = Mock(user=self.user)
        self.assertFalse(self.permission.has_object_permission(request, None, self.other))


class IsAdminRolePermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass-word-123!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="clientuser@example.com", password="pass-word-123!"
        )
        self.permission = IsAdminRole()

    def test_allows_admin_role(self):
        request = Mock(user=self.admin)
        self.assertTrue(self.permission.has_permission(request, None))

    def test_denies_non_admin_role(self):
        request = Mock(user=self.client_user)
        self.assertFalse(self.permission.has_permission(request, None))

    def test_denies_unauthenticated_request(self):
        anonymous = Mock(is_authenticated=False)
        request = Mock(user=anonymous)
        self.assertFalse(self.permission.has_permission(request, None))


class PasswordSecurityTests(TestCase):
    def test_common_password_is_rejected_at_registration(self):
        from apps.accounts.serializers import RegisterSerializer

        serializer = RegisterSerializer(
            data={
                "email": "weakpass@example.com",
                "password": "password",
                "password_confirm": "password",
                "role": "client",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_password_similar_to_email_is_rejected(self):
        from apps.accounts.serializers import RegisterSerializer

        serializer = RegisterSerializer(
            data={
                "email": "similaruser@example.com",
                "password": "similaruser@example.com",
                "password_confirm": "similaruser@example.com",
                "role": "client",
            }
        )
        self.assertFalse(serializer.is_valid())
