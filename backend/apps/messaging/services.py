"""
Messaging and notification business logic.

Isolated from views/serializers, same convention as
apps.businesses.services / apps.services.services / apps.jobs.services
/ apps.marketplace.services.

`notify()` is the single reusable entry point other domain apps call
(from their own services.py, additively — see apps.businesses.services,
apps.jobs.services, apps.marketplace.services) to create an in-app
notification. It has no knowledge of *why* it's being called; each
domain decides when to call it.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Conversation, ConversationParticipant, Message, Notification

# ---------------------------------------------------------------------------
# Conversations / messages
# ---------------------------------------------------------------------------


def start_conversation(
    initiator, recipient, related_job=None, related_listing=None, initial_message=None
):
    """
    Creates a new conversation between initiator and recipient (both
    added as participants) and, if provided, sends the first message.

    Repeat conversations with the same recipient are allowed and not
    collapsed into an existing thread — this is a deliberate choice
    (see the Phase 8 plan), not an oversight.
    """
    if recipient.id == initiator.id:
        raise ValidationError("You cannot start a conversation with yourself.")

    conversation = Conversation.objects.create(
        related_job=related_job, related_listing=related_listing
    )
    ConversationParticipant.objects.create(conversation=conversation, user=initiator)
    ConversationParticipant.objects.create(conversation=conversation, user=recipient)

    if initial_message:
        send_message(conversation, initiator, initial_message)

    return conversation


def send_message(conversation: Conversation, sender, body: str) -> Message:
    """
    Sends a message into `conversation` as `sender`, who must already
    be a participant — this is the enforcement point for "users can
    only send messages to conversations they participate in" (the
    view layer also queryset-scopes for defense in depth).

    Notifies every other participant of the new message.
    """
    is_participant = ConversationParticipant.objects.filter(
        conversation=conversation, user=sender
    ).exists()
    if not is_participant:
        raise ValidationError("You are not a participant in this conversation.")

    message = Message.objects.create(conversation=conversation, sender=sender, body=body)
    conversation.save(update_fields=["updated_at"])

    other_participants = conversation.participants.exclude(user=sender).select_related(
        "user"
    )
    for participant in other_participants:
        notify(
            recipient=participant.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="New message",
            body=body[:200],
            related_conversation=conversation,
        )

    return message


def mark_conversation_read(conversation: Conversation, user) -> ConversationParticipant:
    """
    Advances `user`'s own read cursor on `conversation` to now. Only
    ever operates on the caller's own ConversationParticipant row —
    the view layer looks it up scoped to request.user, so there is no
    way to pass another participant's row in here.
    """
    participant = ConversationParticipant.objects.get(conversation=conversation, user=user)
    participant.last_read_at = timezone.now()
    participant.save(update_fields=["last_read_at"])
    return participant


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def notify(recipient, notification_type, title, body="", **related) -> Notification:
    """
    The single entry point for creating a notification. `related`
    accepts any of related_conversation/related_job/related_listing/
    related_business as keyword arguments; callers pass only the ones
    relevant to their event.
    """
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        body=body,
        **related,
    )


def mark_notification_read(notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return notification


def mark_all_notifications_read(user) -> int:
    """Returns the number of notifications updated."""
    return Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
