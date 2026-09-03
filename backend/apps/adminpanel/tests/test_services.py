from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.adminpanel import services
from apps.adminpanel.models import AuditLog


class LogActionServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )

    def test_log_action_creates_entry(self):
        entry = services.log_action(
            actor=self.admin, action="business.approved", target_type="business", target_id=5
        )
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.action, "business.approved")
        self.assertEqual(entry.target_id, 5)

    def test_log_action_with_no_target(self):
        entry = services.log_action(actor=self.admin, action="user.role_changed")
        self.assertEqual(entry.target_type, "")
        self.assertIsNone(entry.target_id)


class ChangeUserRoleServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.other_admin = User.objects.create_user(
            email="other-admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="client@example.com", password="a-strong-passw0rd!"
        )

    def test_admin_can_change_another_users_role(self):
        updated = services.change_user_role(self.admin, self.client_user, User.Role.PROVIDER)
        self.assertEqual(updated.role, User.Role.PROVIDER)

    def test_admin_cannot_change_own_role(self):
        with self.assertRaises(ValidationError):
            services.change_user_role(self.admin, self.admin, User.Role.CLIENT)

    def test_admin_can_promote_another_user_to_admin(self):
        """Promoting someone ELSE to admin is a normal, intended capability."""
        updated = services.change_user_role(self.admin, self.client_user, User.Role.ADMIN)
        self.assertEqual(updated.role, User.Role.ADMIN)

    def test_role_change_creates_audit_log_entry(self):
        services.change_user_role(self.admin, self.client_user, User.Role.PROVIDER)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin, action="user.role_changed", target_id=self.client_user.id
            ).exists()
        )

    def test_own_role_unchanged_after_rejected_self_change(self):
        with self.assertRaises(ValidationError):
            services.change_user_role(self.admin, self.admin, User.Role.CLIENT)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)


class ActivateUserServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.inactive_user = User.objects.create_user(
            email="inactive@example.com", password="a-strong-passw0rd!", is_active=False
        )

    def test_admin_can_activate_inactive_user(self):
        updated = services.activate_user(self.admin, self.inactive_user)
        self.assertTrue(updated.is_active)

    def test_activating_already_active_user_is_rejected(self):
        active_user = User.objects.create_user(
            email="active@example.com", password="a-strong-passw0rd!"
        )
        with self.assertRaises(ValidationError):
            services.activate_user(self.admin, active_user)

    def test_activate_creates_audit_log_entry(self):
        services.activate_user(self.admin, self.inactive_user)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin, action="user.activated", target_id=self.inactive_user.id
            ).exists()
        )


class DeactivateUserServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            email="client@example.com", password="a-strong-passw0rd!"
        )

    def test_admin_can_deactivate_another_user(self):
        updated = services.deactivate_user(self.admin, self.client_user)
        self.assertFalse(updated.is_active)

    def test_admin_cannot_deactivate_own_account(self):
        with self.assertRaises(ValidationError):
            services.deactivate_user(self.admin, self.admin)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_deactivating_already_inactive_user_is_rejected(self):
        self.client_user.is_active = False
        self.client_user.save()
        with self.assertRaises(ValidationError):
            services.deactivate_user(self.admin, self.client_user)

    def test_deactivate_creates_audit_log_entry(self):
        services.deactivate_user(self.admin, self.client_user)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin, action="user.deactivated", target_id=self.client_user.id
            ).exists()
        )
