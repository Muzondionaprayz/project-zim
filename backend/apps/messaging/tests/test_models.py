from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.messaging.models import Conversation, ConversationParticipant, Message, Notification


class ConversationModelTests(TestCase):
    def test_defaults_to_active(self):
        conversation = Conversation.objects.create()
        self.assertTrue(conversation.is_active)

    def test_str_representation(self):
        conversation = Conversation.objects.create()
        self.assertIn(str(conversation.pk), str(conversation))


class ConversationParticipantModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.conversation = Conversation.objects.create()

    def test_duplicate_participant_rejected_at_db_level(self):
        ConversationParticipant.objects.create(conversation=self.conversation, user=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConversationParticipant.objects.create(
                    conversation=self.conversation, user=self.user
                )

    def test_last_read_at_defaults_to_none(self):
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation, user=self.user
        )
        self.assertIsNone(participant.last_read_at)

    def test_deleting_conversation_deletes_participant(self):
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation, user=self.user
        )
        participant_id = participant.id
        self.conversation.delete()
        self.assertFalse(ConversationParticipant.objects.filter(id=participant_id).exists())


class MessageModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.conversation = Conversation.objects.create()

    def test_deleting_conversation_deletes_messages(self):
        message = Message.objects.create(
            conversation=self.conversation, sender=self.user, body="hi"
        )
        message_id = message.id
        self.conversation.delete()
        self.assertFalse(Message.objects.filter(id=message_id).exists())

    def test_deleting_sender_deletes_message(self):
        message = Message.objects.create(
            conversation=self.conversation, sender=self.user, body="hi"
        )
        message_id = message.id
        self.user.delete()
        self.assertFalse(Message.objects.filter(id=message_id).exists())

    def test_ordering_is_chronological(self):
        first = Message.objects.create(conversation=self.conversation, sender=self.user, body="1")
        second = Message.objects.create(conversation=self.conversation, sender=self.user, body="2")
        self.assertEqual(list(self.conversation.messages.all()), [first, second])


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )

    def test_defaults_to_unread(self):
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Test",
        )
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_deleting_recipient_deletes_notification(self):
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Test",
        )
        notification_id = notification.id
        self.user.delete()
        self.assertFalse(Notification.objects.filter(id=notification_id).exists())

    def test_related_job_set_null_on_job_deletion(self):
        from apps.jobs.models import Job

        employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        job = Job.objects.create(employer=employer, title="Job")
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.JOB_APPLICATION_RECEIVED,
            title="Test",
            related_job=job,
        )
        job.delete()
        notification.refresh_from_db()
        self.assertIsNone(notification.related_job)
