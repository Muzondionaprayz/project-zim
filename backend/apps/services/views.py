from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.businesses.models import Business

from . import services
from .models import Service, ServiceCategory
from .permissions import IsServiceOwner
from .serializers import (
    ServiceCategorySerializer,
    ServiceOwnerSerializer,
    ServicePublicDetailSerializer,
    ServicePublicListSerializer,
)


class ServiceCategoryListView(generics.ListAPIView):
    """GET /api/v1/services/categories/ — public list of active service categories."""

    queryset = ServiceCategory.objects.filter(is_active=True)
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class PublicServiceListView(generics.ListAPIView):
    """
    GET /api/v1/services/

    Public catalog of services. The queryset is hard-filtered to
    is_active=True AND business status=APPROVED regardless of any
    query parameter — a service belonging to a non-approved business,
    or one the owner has deactivated, is never reachable here.

    Supports optional filtering via query params: business (id),
    category (slug), city, province (both via the parent business),
    search (matches title/description).
    """

    serializer_class = ServicePublicListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Service.objects.filter(
            is_active=True, business__status=Business.Status.APPROVED
        ).select_related("category", "business", "business__category")

        params = self.request.query_params
        business = params.get("business")
        category = params.get("category")
        city = params.get("city")
        province = params.get("province")
        search = params.get("search")

        if business:
            queryset = queryset.filter(business_id=business)
        if category:
            queryset = queryset.filter(category__slug=category)
        if city:
            queryset = queryset.filter(business__city__iexact=city)
        if province:
            queryset = queryset.filter(business__province__iexact=province)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset


class PublicServiceDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/services/<pk>/

    Uses the same is_active + approved-business queryset as the list
    endpoint, so an inactive service or one on a non-approved
    business 404s rather than leaking its existence or data.
    """

    serializer_class = ServicePublicDetailSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Service.objects.filter(
        is_active=True, business__status=Business.Status.APPROVED
    ).select_related("category", "business", "business__category")


class MyServiceListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/services/my/ — list services across all of the
    authenticated user's own businesses
    POST /api/v1/services/my/ — create a new service

    `business` must be one of the authenticated user's own
    businesses — the serializer's `business` field queryset is
    restricted to request.user's businesses, so a client cannot
    create a service under a business they don't own even by
    guessing a valid business ID.
    """

    serializer_class = ServiceOwnerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Service.objects.filter(
            business__owner=self.request.user
        ).select_related("category", "business")


class MyServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/services/my/<pk>/

    Scoped to services under the authenticated user's own
    businesses. The queryset itself excludes services under other
    users' businesses, so requesting one here 404s rather than
    403s — consistent with not confirming the existence of data that
    isn't yours. IsServiceOwner is kept as an explicit second layer
    of defense.
    """

    serializer_class = ServiceOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsServiceOwner]

    def get_queryset(self):
        return Service.objects.filter(
            business__owner=self.request.user
        ).select_related("category", "business")


class ActivateServiceView(APIView):
    """
    POST /api/v1/services/my/<pk>/activate/

    Owner action: publishes the service. Rejected (400) if the
    parent business is not currently approved.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk, business__owner=request.user)
        try:
            services.activate_service(service)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(ServiceOwnerSerializer(service).data)


class DeactivateServiceView(APIView):
    """POST /api/v1/services/my/<pk>/deactivate/ — owner action: unpublishes the service."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk, business__owner=request.user)
        services.deactivate_service(service)
        return Response(ServiceOwnerSerializer(service).data)
