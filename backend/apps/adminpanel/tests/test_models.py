from django.test import TestCase

from apps.accounts.models import User
from apps.adminpanel.models import AuditLog


class AuditLogModelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )

    def test_defaults(self):
        entry = AuditLog.objects.create(actor=self.admin, action="test.action")
        self.assertEqual(entry.target_type, "")
        self.assertIsNone(entry.target_id)
        self.assertEqual(entry.details, "")

    def test_deleting_actor_preserves_log_entry(self):
        entry = AuditLog.objects.create(actor=self.admin, action="test.action")
        entry_id = entry.id
        self.admin.delete()
        entry.refresh_from_db()
        self.assertTrue(AuditLog.objects.filter(id=entry_id).exists())
        self.assertIsNone(entry.actor)

    def test_str_representation(self):
        entry = AuditLog.objects.create(actor=self.admin, action="test.action")
        self.assertIn("test.action", str(entry))

    def test_ordering_is_newest_first(self):
        first = AuditLog.objects.create(actor=self.admin, action="first")
        second = AuditLog.objects.create(actor=self.admin, action="second")
        entries = list(AuditLog.objects.all())
        self.assertEqual(entries, [second, first])
