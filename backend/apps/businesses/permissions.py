from rest_framework.permissions import BasePermission


class IsBusinessOwner(BasePermission):
    """
    Object-level permission: only the business's own owner may modify
    or delete it. Defense in depth alongside the owner-scoped queryset
    in the view — either one alone would already prevent cross-owner
    access, but both together make the intent explicit.
    """

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id
