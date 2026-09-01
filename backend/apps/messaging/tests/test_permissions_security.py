from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.messaging import services
from apps.messaging.models import Notification
from apps.messaging.permissions import IsConversationParticipant, IsNotificationOwner


class IsConversationParticipantPermissionTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", password="a-strong-passw0rd!"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="a-strong-passw0rd!"
        )
        self.stranger = User.objects.create_user(
            email="stranger@example.com", password="a-strong-passw0rd!"
        )
        self.conversation = services.start_conversation(self.alice, self.bob)
        self.permission = IsConversationParticipant()

    def test_allows_participant(self):
        request = Mock(user=self.bob)
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.conversation)
        )

    def test_denies_non_participant(self):
        request = Mock(user=self.stranger)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.conversation)
        )


class IsNotificationOwnerPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.notification = services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Test",
        )
        self.permission = IsNotificationOwner()

    def test_allows_recipient(self):
        request = Mock(user=self.user)
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.notification)
        )

    def test_denies_non_recipient(self):
        request = Mock(user=self.other)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.notification)
        )
