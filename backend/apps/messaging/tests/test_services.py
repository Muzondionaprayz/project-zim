from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.messaging import services
from apps.messaging.models import Conversation, ConversationParticipant, Notification


class StartConversationServiceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", password="a-strong-passw0rd!"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="a-strong-passw0rd!"
        )

    def test_creates_conversation_with_both_participants(self):
        conversation = services.start_conversation(self.alice, self.bob)
        participant_users = set(conversation.participants.values_list("user_id", flat=True))
        self.assertEqual(participant_users, {self.alice.id, self.bob.id})

    def test_cannot_start_conversation_with_self(self):
        with self.assertRaises(ValidationError):
            services.start_conversation(self.alice, self.alice)

    def test_initial_message_is_sent(self):
        conversation = services.start_conversation(self.alice, self.bob, initial_message="Hi!")
        self.assertEqual(conversation.messages.count(), 1)
        self.assertEqual(conversation.messages.first().body, "Hi!")
        self.assertEqual(conversation.messages.first().sender, self.alice)

    def test_no_initial_message_means_no_message(self):
        conversation = services.start_conversation(self.alice, self.bob)
        self.assertEqual(conversation.messages.count(), 0)

    def test_repeat_conversations_with_same_recipient_are_allowed(self):
        """Deliberate design choice — conversations are not deduplicated."""
        first = services.start_conversation(self.alice, self.bob)
        second = services.start_conversation(self.alice, self.bob)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(Conversation.objects.count(), 2)

    def test_initial_message_notifies_recipient(self):
        services.start_conversation(self.alice, self.bob, initial_message="Hi!")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.bob, notification_type=Notification.NotificationType.NEW_MESSAGE
            ).exists()
        )


class SendMessageServiceTests(TestCase):
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

    def test_participant_can_send_message(self):
        message = services.send_message(self.conversation, self.bob, "Hello back")
        self.assertEqual(message.sender, self.bob)
        self.assertEqual(message.body, "Hello back")

    def test_non_participant_cannot_send_message(self):
        with self.assertRaises(ValidationError):
            services.send_message(self.conversation, self.stranger, "Sneaky")

    def test_sending_message_notifies_other_participant_only(self):
        services.send_message(self.conversation, self.alice, "Hi Bob")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.bob, notification_type=Notification.NotificationType.NEW_MESSAGE
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.alice, notification_type=Notification.NotificationType.NEW_MESSAGE
            ).exists()
        )

    def test_sending_message_updates_conversation_timestamp(self):
        original_updated_at = self.conversation.updated_at
        services.send_message(self.conversation, self.alice, "Hi")
        self.conversation.refresh_from_db()
        self.assertGreater(self.conversation.updated_at, original_updated_at)


class MarkConversationReadServiceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", password="a-strong-passw0rd!"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="a-strong-passw0rd!"
        )
        self.conversation = services.start_conversation(self.alice, self.bob)

    def test_marks_own_cursor(self):
        participant = services.mark_conversation_read(self.conversation, self.bob)
        self.assertIsNotNone(participant.last_read_at)
        self.assertEqual(participant.user, self.bob)

    def test_does_not_affect_other_participants_cursor(self):
        services.mark_conversation_read(self.conversation, self.bob)
        alice_participant = ConversationParticipant.objects.get(
            conversation=self.conversation, user=self.alice
        )
        self.assertIsNone(alice_participant.last_read_at)


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )

    def test_notify_creates_notification(self):
        notification = services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Test",
            body="Body text",
        )
        self.assertEqual(notification.recipient, self.user)
        self.assertFalse(notification.is_read)

    def test_mark_notification_read_sets_timestamp(self):
        notification = services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Test",
        )
        services.mark_notification_read(notification)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_mark_notification_read_is_idempotent(self):
        notification = services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Test",
        )
        services.mark_notification_read(notification)
        first_read_at = notification.read_at
        services.mark_notification_read(notification)
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, first_read_at)

    def test_mark_all_notifications_read_only_affects_target_user(self):
        other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Mine",
        )
        services.notify(
            recipient=other_user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Theirs",
        )
        count = services.mark_all_notifications_read(self.user)
        self.assertEqual(count, 1)
        self.assertFalse(
            Notification.objects.get(recipient=other_user, title="Theirs").is_read
        )
