from rest_framework.permissions import BasePermission


class IsConversationParticipant(BasePermission):
    """Object-level permission: only a participant of the conversation may access it."""

    def has_object_permission(self, request, view, obj):
        return obj.participants.filter(user=request.user).exists()


class IsNotificationOwner(BasePermission):
    """Object-level permission: only the notification's own recipient may access it."""

    def has_object_permission(self, request, view, obj):
        return obj.recipient_id == request.user.id
