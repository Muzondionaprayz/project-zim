from rest_framework.permissions import BasePermission


class IsListingOwner(BasePermission):
    """Object-level permission: only the listing's own seller may modify or delete it."""

    def has_object_permission(self, request, view, obj):
        return obj.seller_id == request.user.id


class IsListingImageOwner(BasePermission):
    """Object-level permission: only the parent listing's seller may modify/delete an image."""

    def has_object_permission(self, request, view, obj):
        return obj.listing.seller_id == request.user.id
