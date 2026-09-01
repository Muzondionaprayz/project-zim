from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.jobs.models import Job
from apps.messaging import services


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class StartConversationAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", password="a-strong-passw0rd!"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="a-strong-passw0rd!"
        )
        self.url = reverse("messaging:conversation-list")

    def test_unauthenticated_cannot_start_conversation(self):
        response = self.client.post(self.url, {"recipient_id": self.bob.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_start_conversation(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"recipient_id": self.bob.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_start_conversation_with_self(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"recipient_id": self.alice.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_recipient_returns_400(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"recipient_id": 999999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_conversation_with_initial_message_creates_message(self):
        self.authenticate_as(self.alice)
        response = self.client.post(
            self.url, {"recipient_id": self.bob.id, "initial_message": "Hey there"}
        )
        self.assertEqual(response.data["last_message"]["body"], "Hey there")

    def test_other_participant_field_shows_recipient_not_self(self):
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"recipient_id": self.bob.id})
        self.assertEqual(response.data["other_participant"]["email"], "bob@example.com")

    def test_response_never_contains_participant_ids_field(self):
        """There is no writable/exposed raw participant-ID list — only the derived other_participant."""
        self.authenticate_as(self.alice)
        response = self.client.post(self.url, {"recipient_id": self.bob.id})
        self.assertNotIn("participants", response.data)

    def test_can_link_conversation_to_a_job(self):
        job = Job.objects.create(employer=self.bob, title="Job", status=Job.Status.OPEN)
        self.authenticate_as(self.alice)
        response = self.client.post(
            self.url, {"recipient_id": self.bob.id, "related_job": job.id}
        )
        self.assertEqual(response.data["related_job"], job.id)

    def test_repeat_conversations_are_allowed_not_deduplicated(self):
        self.authenticate_as(self.alice)
        first = self.client.post(self.url, {"recipient_id": self.bob.id})
        second = self.client.post(self.url, {"recipient_id": self.bob.id})
        self.assertNotEqual(first.data["id"], second.data["id"])


class ConversationListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", password="a-strong-passw0rd!"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="a-strong-passw0rd!"
        )
        self.charlie = User.objects.create_user(
            email="charlie@example.com", password="a-strong-passw0rd!"
        )
        self.alice_bob_conv = services.start_conversation(self.alice, self.bob)
        self.bob_charlie_conv = services.start_conversation(self.bob, self.charlie)
        self.url = reverse("messaging:conversation-list")

    def test_list_only_returns_own_conversations(self):
        self.authenticate_as(self.alice)
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.alice_bob_conv.id])

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ConversationDetailAPITests(AuthenticatedAPITestCase):
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

    def test_participant_can_view_conversation(self):
        self.authenticate_as(self.bob)
        url = reverse("messaging:conversation-detail", kwargs={"pk": self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_participant_cannot_view_conversation(self):
        self.authenticate_as(self.stranger)
        url = reverse("messaging:conversation-detail", kwargs={"pk": self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_view_conversation(self):
        url = reverse("messaging:conversation-detail", kwargs={"pk": self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_conversation_returns_404(self):
        self.authenticate_as(self.alice)
        url = reverse("messaging:conversation-detail", kwargs={"pk": 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
