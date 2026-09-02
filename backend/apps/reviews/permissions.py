from rest_framework.permissions import BasePermission


class IsReviewOwner(BasePermission):
    """Object-level permission: only the review's own author may modify or delete it."""

    def has_object_permission(self, request, view, obj):
        return obj.reviewer_id == request.user.id
