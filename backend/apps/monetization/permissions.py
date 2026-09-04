from rest_framework.permissions import BasePermission


class IsSubscriptionOwner(BasePermission):
    """Object-level permission: only the subscription's own user may access it."""

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id


class IsTransactionOwner(BasePermission):
    """Object-level permission: only the owner of the parent subscription may access it."""

    def has_object_permission(self, request, view, obj):
        return obj.subscription.user_id == request.user.id
