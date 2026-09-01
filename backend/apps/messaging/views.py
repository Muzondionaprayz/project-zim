from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Conversation, Notification
from .permissions import IsConversationParticipant, IsNotificationOwner
from .serializers import (
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    NotificationSerializer,
    StartConversationSerializer,
)


class ConversationListCreateView(generics.ListAPIView):
    """
    GET  /api/v1/messaging/conversations/ — list the authenticated
    user's own conversations
    POST /api/v1/messaging/conversations/ — start a new conversation

    Ownership/membership always comes from request.user; the
    recipient is validated to exist and not be the caller themself
    (see services.start_conversation). Repeat conversations with the
    same recipient are allowed by design, not deduplicated.
    """

    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Conversation.objects.filter(participants__user=self.request.user)
            .distinct()
            .prefetch_related("participants__user", "messages")
        )

    def get_serializer_context(self):
        return {"request": self.request}

    def post(self, request, *args, **kwargs):
        serializer = StartConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            conversation = services.start_conversation(
                initiator=request.user,
                recipient=serializer.validated_data["recipient"],
                related_job=serializer.validated_data.get("related_job"),
                related_listing=serializer.validated_data.get("related_listing"),
                initial_message=serializer.validated_data.get("initial_message"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        output = ConversationSerializer(conversation, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class ConversationDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/messaging/conversations/<pk>/

    Scoped to the authenticated user's own conversations. A
    conversation ID the user isn't part of 404s rather than 403s,
    consistent with the project's established pattern.
    """

    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated, IsConversationParticipant]

    def get_queryset(self):
        return Conversation.objects.filter(
            participants__user=self.request.user
        ).distinct().prefetch_related("participants__user", "messages")

    def get_serializer_context(self):
        return {"request": self.request}


class ConversationMessageListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/messaging/conversations/<pk>/messages/ — list messages
    POST /api/v1/messaging/conversations/<pk>/messages/ — send a message

    The conversation lookup itself is scoped to participants of the
    requesting user, so a non-participant gets a 404 before any
    message read/write is attempted. `sender` always comes from
    request.user via services.send_message — never from client input.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_conversation(self):
        return get_object_or_404(
            Conversation, pk=self.kwargs["pk"], participants__user=self.request.user
        )

    def get_queryset(self):
        return self.get_conversation().messages.select_related("sender")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MessageCreateSerializer
        return MessageSerializer

    def create(self, request, *args, **kwargs):
        conversation = self.get_conversation()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = services.send_message(
                conversation, request.user, serializer.validated_data["body"]
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        output = MessageSerializer(message)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MarkConversationReadView(APIView):
    """
    POST /api/v1/messaging/conversations/<pk>/read/

    Advances only the caller's own read cursor — the conversation
    lookup is scoped to request.user's own participation, so there is
    no way to affect another participant's cursor.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = get_object_or_404(
            Conversation, pk=pk, participants__user=request.user
        )
        services.mark_conversation_read(conversation, request.user)
        return Response(
            ConversationSerializer(conversation, context={"request": request}).data
        )


class NotificationListView(generics.ListAPIView):
    """GET /api/v1/notifications/ — list the authenticated user's own notifications."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class MarkNotificationReadView(APIView):
    """
    POST /api/v1/notifications/<pk>/read/

    Scoped to the caller's own notifications; another user's
    notification ID 404s rather than 403s.
    """

    permission_classes = [permissions.IsAuthenticated, IsNotificationOwner]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        services.mark_notification_read(notification)
        return Response(NotificationSerializer(notification).data)


class MarkAllNotificationsReadView(APIView):
    """POST /api/v1/notifications/read-all/ — marks only the caller's own notifications read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        count = services.mark_all_notifications_read(request.user)
        return Response({"marked_read": count})
