from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole

from . import services
from .models import Business, BusinessCategory
from .permissions import IsBusinessOwner
from .serializers import (
    BusinessCategorySerializer,
    BusinessOwnerSerializer,
    BusinessPublicDetailSerializer,
    BusinessPublicListSerializer,
    VerificationActionSerializer,
)


class BusinessCategoryListView(generics.ListAPIView):
    """GET /api/v1/businesses/categories/ — public list of active categories."""

    queryset = BusinessCategory.objects.filter(is_active=True)
    serializer_class = BusinessCategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class PublicBusinessListView(generics.ListAPIView):
    """
    GET /api/v1/businesses/

    Public catalog of businesses. The queryset is hard-filtered to
    status=APPROVED regardless of any query parameter — draft,
    pending, rejected, changes-requested, and suspended businesses
    are never reachable here.

    Supports optional filtering via query params: category (slug),
    city, province, search (matches name/description).
    """

    serializer_class = BusinessPublicListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Business.objects.filter(
            status=Business.Status.APPROVED
        ).select_related("category")

        params = self.request.query_params
        category = params.get("category")
        city = params.get("city")
        province = params.get("province")
        search = params.get("search")

        if category:
            queryset = queryset.filter(category__slug=category)
        if city:
            queryset = queryset.filter(city__iexact=city)
        if province:
            queryset = queryset.filter(province__iexact=province)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        return queryset


class PublicBusinessDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/businesses/<pk>/

    Public detail view. Uses the same APPROVED-only queryset as the
    list endpoint, so a non-approved business ID 404s rather than
    leaking its existence or data.
    """

    serializer_class = BusinessPublicDetailSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Business.objects.filter(
        status=Business.Status.APPROVED
    ).select_related("category")


class MyBusinessListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/businesses/my/ — list the authenticated user's own businesses
    POST /api/v1/businesses/my/ — create a new business

    Ownership always comes from request.user via perform_create.
    There is no writable `owner` field on the serializer, so any
    "owner" key in the request body is simply ignored by DRF.
    """

    serializer_class = BusinessOwnerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Business.objects.filter(owner=self.request.user).select_related(
            "category"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MyBusinessDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/businesses/my/<pk>/

    Scoped to the authenticated user's own businesses. The queryset
    itself excludes other users' businesses, so requesting another
    user's business ID here 404s rather than 403s — consistent with
    not confirming the existence of data that isn't yours.
    IsBusinessOwner is kept as an explicit second layer of defense.
    """

    serializer_class = BusinessOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessOwner]

    def get_queryset(self):
        return Business.objects.filter(owner=self.request.user).select_related(
            "category"
        )


class SubmitForVerificationView(APIView):
    """
    POST /api/v1/businesses/my/<pk>/submit/

    Owner action: moves their own draft/changes-requested business
    into the pending-verification queue.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk, owner=request.user)
        try:
            services.submit_for_verification(business)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(BusinessOwnerSerializer(business).data)


class ApproveBusinessView(APIView):
    """POST /api/v1/businesses/admin/<pk>/approve/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.approve_business(
                business, notes=serializer.validated_data.get("notes", "")
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(BusinessOwnerSerializer(business).data)


class RejectBusinessView(APIView):
    """POST /api/v1/businesses/admin/<pk>/reject/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.reject_business(
                business, notes=serializer.validated_data.get("notes", "")
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(BusinessOwnerSerializer(business).data)


class RequestChangesView(APIView):
    """POST /api/v1/businesses/admin/<pk>/request-changes/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.request_changes(
                business, notes=serializer.validated_data.get("notes", "")
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(BusinessOwnerSerializer(business).data)


class SuspendBusinessView(APIView):
    """POST /api/v1/businesses/admin/<pk>/suspend/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.suspend_business(
                business, notes=serializer.validated_data.get("notes", "")
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(BusinessOwnerSerializer(business).data)


class RestoreBusinessView(APIView):
    """POST /api/v1/businesses/admin/<pk>/restore/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.restore_business(
                business, notes=serializer.validated_data.get("notes", "")
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(BusinessOwnerSerializer(business).data)
