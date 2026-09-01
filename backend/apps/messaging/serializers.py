from rest_framework import serializers

from apps.accounts.models import User
from apps.jobs.models import Job
from apps.marketplace.models import MarketplaceListing

from .models import Conversation, Message, Notification


class ParticipantSummarySerializer(serializers.ModelSerializer):
    """
    Minimal identity info about the other participant in a
    conversation. Shown only to someone who already shares a
    conversation with them — never on any public endpoint.
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


class MessageSerializer(serializers.ModelSerializer):
    """
    Read representation of a message. `sender` is never writable —
    it is set only from request.user in the view layer.
    """

    sender = ParticipantSummarySerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "sender", "body", "created_at"]


class MessageCreateSerializer(serializers.Serializer):
    """Input shape for sending a message; the view supplies conversation and sender."""

    body = serializers.CharField(allow_blank=False)


class StartConversationSerializer(serializers.Serializer):
    """
    Input shape for starting a conversation. Not a ModelSerializer —
    `recipient_id` maps to a participant, not a Conversation field,
    and `initial_message` maps to a Message, not the Conversation
    itself.
    """

    recipient_id = serializers.PrimaryKeyRelatedField(
        source="recipient", queryset=User.objects.all()
    )
    related_job = serializers.PrimaryKeyRelatedField(
        queryset=Job.objects.all(), required=False, allow_null=True
    )
    related_listing = serializers.PrimaryKeyRelatedField(
        queryset=MarketplaceListing.objects.all(), required=False, allow_null=True
    )
    initial_message = serializers.CharField(required=False, allow_blank=True, default="")


class ConversationSerializer(serializers.ModelSerializer):
    """
    Read representation of a conversation, from the perspective of
    request.user (required in context). Never exposes the full
    participant list with account details beyond the other
    participant's own summary.
    """

    other_participant = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "related_job",
            "related_listing",
            "is_active",
            "other_participant",
            "unread_count",
            "last_message",
            "created_at",
            "updated_at",
        ]

    def get_other_participant(self, obj):
        request = self.context["request"]
        participant = (
            obj.participants.exclude(user=request.user).select_related("user").first()
        )
        return ParticipantSummarySerializer(participant.user).data if participant else None

    def get_unread_count(self, obj):
        request = self.context["request"]
        own = obj.participants.filter(user=request.user).first()
        qs = obj.messages.exclude(sender=request.user)
        if own and own.last_read_at:
            qs = qs.filter(created_at__gt=own.last_read_at)
        return qs.count()

    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        return MessageSerializer(message).data if message else None


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "body",
            "related_conversation",
            "related_job",
            "related_listing",
            "related_business",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
