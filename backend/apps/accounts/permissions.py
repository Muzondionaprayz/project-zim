from rest_framework.permissions import BasePermission


class IsSelf(BasePermission):
    """Object-level permission: only the user themself may access it."""

    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsAdminRole(BasePermission):
    """Grants access only to users whose role is ADMIN (platform staff)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_role
        )
