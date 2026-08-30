from rest_framework.permissions import BasePermission


class IsJobOwner(BasePermission):
    """Object-level permission: only the job's own employer may modify or delete it."""

    def has_object_permission(self, request, view, obj):
        return obj.employer_id == request.user.id


class IsApplicationOwner(BasePermission):
    """Object-level permission: only the application's own applicant may access it."""

    def has_object_permission(self, request, view, obj):
        return obj.applicant_id == request.user.id
