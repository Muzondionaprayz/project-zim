from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User, UserProfile


class UserModelTests(TestCase):
    def test_create_user_with_email_and_password(self):
        user = User.objects.create_user(email="jane@example.com", password="s3cure-pass!")
        self.assertEqual(user.email, "jane@example.com")
        self.assertTrue(user.check_password("s3cure-pass!"))
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="whatever123")

    def test_email_is_normalized(self):
        user = User.objects.create_user(email="Jane@EXAMPLE.com", password="s3cure-pass!")
        self.assertEqual(user.email, "Jane@example.com")

    def test_email_is_unique(self):
        User.objects.create_user(email="dupe@example.com", password="s3cure-pass!")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email="dupe@example.com", password="another-pass!")

    def test_create_superuser_sets_admin_role_and_flags(self):
        admin = User.objects.create_superuser(email="root@example.com", password="s3cure-pass!")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_create_superuser_rejects_is_staff_false(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="root2@example.com", password="s3cure-pass!", is_staff=False
            )

    def test_password_is_hashed_not_stored_in_plaintext(self):
        user = User.objects.create_user(email="hash@example.com", password="s3cure-pass!")
        self.assertNotEqual(user.password, "s3cure-pass!")
        self.assertTrue(user.password.startswith("pbkdf2_") or "$" in user.password)

    def test_is_provider_property(self):
        provider = User.objects.create_user(
            email="provider@example.com", password="s3cure-pass!", role=User.Role.PROVIDER
        )
        client = User.objects.create_user(
            email="client@example.com", password="s3cure-pass!"
        )
        self.assertTrue(provider.is_provider)
        self.assertFalse(client.is_provider)

    def test_str_returns_email(self):
        user = User.objects.create_user(email="strme@example.com", password="s3cure-pass!")
        self.assertEqual(str(user), "strme@example.com")


class UserProfileSignalTests(TestCase):
    def test_profile_is_created_automatically_for_new_user(self):
        user = User.objects.create_user(email="withprofile@example.com", password="s3cure-pass!")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.user, user)

    def test_deleting_user_deletes_profile(self):
        user = User.objects.create_user(email="deleteme@example.com", password="s3cure-pass!")
        profile_id = user.profile.id
        user.delete()
        self.assertFalse(UserProfile.objects.filter(id=profile_id).exists())
