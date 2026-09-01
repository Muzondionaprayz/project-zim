from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.messaging import services
from apps.messaging.models import ConversationParticipant


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class SendMessageAPITests(AuthenticatedAPITestCase):
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
        self.url = reverse(
            "messaging:conversation-messages", kwargs={"pk": self.conversation.pk}
        )

    def test_unauthenticated_cannot_send_message(self):
        response = self.client.post(self.url, {"body": "Hi"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_participant_can_send_message(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"body": "Hi Bob"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sender_is_derived_from_request_user(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"body": "Hi Bob"})
        self.assertEqual(response.data["sender"]["email"], "alice@example.com")

    def test_client_cannot_spoof_sender(self):
        """
        There is no writable "sender" field at all — even if supplied,
        the message must be attributed to request.user, never to the
        spoofed ID.
        """
        self.authenticate_as(self.alice)
        response = self.client.post(
            self.url, {"body": "Hi Bob", "sender": self.bob.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["sender"]["email"], "alice@example.com")

    def test_non_participant_cannot_send_message(self):
        self.authenticate_as(self.stranger)
        response = self.client.post(self.url, {"body": "Sneaky"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_participant_cannot_send_by_spoofing_conversation_id(self):
        """Even with the real, valid conversation ID, a non-participant is blocked."""
        self.authenticate_as(self.stranger)
        response = self.client.post(self.url, {"body": "I'm in!"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_empty_body_is_rejected(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"body": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MessageListAPITests(AuthenticatedAPITestCase):
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
        self.conversation = services.start_conversation(
            self.alice, self.bob, initial_message="Hi"
        )
        self.url = reverse(
            "messaging:conversation-messages", kwargs={"pk": self.conversation.pk}
        )

    def test_participant_can_list_messages(self):
        self.authenticate_as(self.bob)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_non_participant_cannot_list_messages(self):
        self.authenticate_as(self.stranger)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_list_messages(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_edit_or_delete_endpoint_exists_for_messages(self):
        """Messages are immutable this phase — there is no message detail/update/delete route."""
        from django.urls import NoReverseMatch

        with self.assertRaises(NoReverseMatch):
            reverse("messaging:message-detail", kwargs={"pk": 1})


class MarkConversationReadAPITests(AuthenticatedAPITestCase):
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
        self.conversation = services.start_conversation(
            self.alice, self.bob, initial_message="Hi"
        )
        self.url = reverse(
            "messaging:conversation-read", kwargs={"pk": self.conversation.pk}
        )

    def test_participant_can_mark_own_cursor_read(self):
        self.authenticate_as(self.bob)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bob_participant = ConversationParticipant.objects.get(
            conversation=self.conversation, user=self.bob
        )
        self.assertIsNotNone(bob_participant.last_read_at)

    def test_marking_read_does_not_affect_other_participant(self):
        self.authenticate_as(self.bob)
        self.client.post(self.url)
        alice_participant = ConversationParticipant.objects.get(
            conversation=self.conversation, user=self.alice
        )
        self.assertIsNone(alice_participant.last_read_at)

    def test_non_participant_cannot_mark_read(self):
        self.authenticate_as(self.stranger)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_mark_read(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unread_count_drops_to_zero_after_marking_read(self):
        self.authenticate_as(self.bob)
        detail_url = reverse(
            "messaging:conversation-detail", kwargs={"pk": self.conversation.pk}
        )
        before = self.client.get(detail_url)
        self.assertEqual(before.data["unread_count"], 1)

        self.client.post(self.url)

        after = self.client.get(detail_url)
        self.assertEqual(after.data["unread_count"], 0)
