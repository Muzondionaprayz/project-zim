from rest_framework.permissions import BasePermission


class IsServiceOwner(BasePermission):
    """
    Object-level permission: only the owner of a service's parent
    business may modify or delete that service. There is no
    independent "service owner" — ownership is always transitive
    through obj.business.owner.
    """

    def has_object_permission(self, request, view, obj):
        return obj.business.owner_id == request.user.id
