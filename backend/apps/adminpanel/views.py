from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAdminRole
from apps.businesses.models import Business
from apps.marketplace.models import MarketplaceListing
from apps.reviews.models import Review

from . import services
from .models import AuditLog
from .serializers import (
    AdminBusinessSerializer,
    AdminMarketplaceListingSerializer,
    AdminReviewSerializer,
    AdminUserSerializer,
    AuditLogSerializer,
    ChangeUserRoleSerializer,
)

# ---------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------


class AdminUserListView(generics.ListAPIView):
    """
    GET /api/v1/admin/users/

    Admin-only. Filterable by role, is_active, and a simple email
    search. Nothing here trusts client-supplied identity — access is
    gated purely by request.user.is_admin_role via IsAdminRole.
    """

    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = User.objects.all()
        params = self.request.query_params
        if params.get("role"):
            queryset = queryset.filter(role=params["role"])
        if params.get("is_active") is not None and params.get("is_active") != "":
            is_active = params["is_active"].lower() in ("true", "1")
            queryset = queryset.filter(is_active=is_active)
        if params.get("search"):
            queryset = queryset.filter(email__icontains=params["search"])
        return queryset


class AdminUserDetailView(generics.RetrieveAPIView):
    """GET /api/v1/admin/users/<pk>/ — admin-only."""

    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]


class AdminChangeUserRoleView(APIView):
    """
    POST /api/v1/admin/users/<pk>/role/ — admin-only.

    Refuses to let an admin change their own role (self-demotion/
    lockout guard) — see apps.adminpanel.services.change_user_role.
    """

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        serializer = ChangeUserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.change_user_role(
                request.user, target_user, serializer.validated_data["role"]
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminUserSerializer(target_user).data)


class AdminActivateUserView(APIView):
    """POST /api/v1/admin/users/<pk>/activate/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        try:
            services.activate_user(request.user, target_user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminUserSerializer(target_user).data)


class AdminDeactivateUserView(APIView):
    """
    POST /api/v1/admin/users/<pk>/deactivate/ — admin-only.

    Refuses to let an admin deactivate their own account (self-
    lockout guard) — see apps.adminpanel.services.deactivate_user.
    """

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        try:
            services.deactivate_user(request.user, target_user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminUserSerializer(target_user).data)


# ---------------------------------------------------------------------------
# Cross-domain admin visibility (read-only; moderation actions remain
# on their existing domain endpoints — see the Phase 10 report for why
# these are not duplicated here)
# ---------------------------------------------------------------------------


class AdminBusinessListView(generics.ListAPIView):
    """
    GET /api/v1/admin/businesses/

    All businesses regardless of status, filterable by status — the
    visibility this project didn't have before Phase 10 (Business's
    own "my/" endpoint is owner-scoped, and the public endpoint only
    ever shows approved businesses). Moderation itself still happens
    via the existing /api/v1/businesses/admin/<pk>/{approve,...}/
    endpoints from Phase 3 — not duplicated here.
    """

    serializer_class = AdminBusinessSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = Business.objects.all().select_related("owner", "category")
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


class AdminMarketplaceListingListView(generics.ListAPIView):
    """
    GET /api/v1/admin/marketplace-listings/

    All listings regardless of status/moderation_status. Moderation
    actions remain on the existing Phase 6
    /api/v1/marketplace/admin/<pk>/{approve,...}/ endpoints.
    """

    serializer_class = AdminMarketplaceListingSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = MarketplaceListing.objects.all().select_related("seller", "category")
        params = self.request.query_params
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("moderation_status"):
            queryset = queryset.filter(moderation_status=params["moderation_status"])
        return queryset


class AdminReviewListView(generics.ListAPIView):
    """
    GET /api/v1/admin/reviews/

    All reviews regardless of status. Moderation actions remain on
    the existing Phase 9 /api/v1/reviews/admin/<pk>/{hide,restore}/
    endpoints.
    """

    serializer_class = AdminReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = Review.objects.all().select_related(
            "reviewer", "business", "service", "marketplace_listing"
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


# ---------------------------------------------------------------------------
# Audit log visibility
# ---------------------------------------------------------------------------


class AdminAuditLogListView(generics.ListAPIView):
    """
    GET /api/v1/admin/audit-logs/

    Read-only. Filterable by action and target_type. There is no
    write endpoint — entries are only ever created by log_action()
    calls from within services.py files, never directly by a client.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = AuditLog.objects.all().select_related("actor")
        params = self.request.query_params
        if params.get("action"):
            queryset = queryset.filter(action=params["action"])
        if params.get("target_type"):
            queryset = queryset.filter(target_type=params["target_type"])
        return queryset
