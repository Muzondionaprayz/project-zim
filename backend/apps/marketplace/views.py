from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole

from . import services
from .models import ListingImage, MarketplaceCategory, MarketplaceListing
from .permissions import IsListingImageOwner, IsListingOwner
from .serializers import (
    ListingImageOwnerSerializer,
    MarketplaceCategorySerializer,
    MarketplaceListingOwnerSerializer,
    MarketplaceListingPublicDetailSerializer,
    MarketplaceListingPublicListSerializer,
)


class MarketplaceCategoryListView(generics.ListAPIView):
    """GET /api/v1/marketplace/categories/ — public list of active categories."""

    queryset = MarketplaceCategory.objects.filter(is_active=True)
    serializer_class = MarketplaceCategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


def _public_queryset():
    return MarketplaceListing.objects.filter(
        status=MarketplaceListing.Status.PUBLISHED,
        moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
    ).select_related("category").prefetch_related("images")


class PublicListingListView(generics.ListAPIView):
    """
    GET /api/v1/marketplace/

    Public catalog. Hard-filtered to status=PUBLISHED AND
    moderation_status=APPROVED regardless of any query parameter.
    Filterable by category (slug), city, province, search
    (title/description).
    """

    serializer_class = MarketplaceListingPublicListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = _public_queryset()
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
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        return queryset


class PublicListingDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/marketplace/<pk>/

    Uses the same published+approved queryset as the list endpoint,
    so a draft/unapproved/suspended listing 404s rather than leaking
    its existence or data.
    """

    serializer_class = MarketplaceListingPublicDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return _public_queryset()


class MyListingListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/marketplace/my/ — list the authenticated user's own listings
    POST /api/v1/marketplace/my/ — create a new listing

    Ownership always comes from request.user via perform_create.
    """

    serializer_class = MarketplaceListingOwnerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MarketplaceListing.objects.filter(
            seller=self.request.user
        ).select_related("category").prefetch_related("images")

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class MyListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/marketplace/my/<pk>/

    Scoped to the authenticated user's own listings. IsListingOwner
    kept as an explicit second layer of defense.
    """

    serializer_class = MarketplaceListingOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsListingOwner]

    def get_queryset(self):
        return MarketplaceListing.objects.filter(
            seller=self.request.user
        ).select_related("category").prefetch_related("images")


class PublishListingView(APIView):
    """POST /api/v1/marketplace/my/<pk>/publish/ — seller action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        listing = get_object_or_404(MarketplaceListing, pk=pk, seller=request.user)
        try:
            services.publish_listing(listing)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(MarketplaceListingOwnerSerializer(listing).data)


class UnpublishListingView(APIView):
    """POST /api/v1/marketplace/my/<pk>/unpublish/ — seller action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        listing = get_object_or_404(MarketplaceListing, pk=pk, seller=request.user)
        try:
            services.unpublish_listing(listing)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(MarketplaceListingOwnerSerializer(listing).data)


class MyListingImageListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/marketplace/my/images/ — list images across the
    authenticated user's own listings
    POST /api/v1/marketplace/my/images/ — add an image to one of
    their own listings

    `listing`'s field queryset is restricted to the requester's own
    listings, so a client cannot attach an image to a listing they
    don't own even by guessing a valid ID. Creation is routed through
    services.add_listing_image, which enforces the 10-image cap and
    sets is_primary for the first image.
    """

    serializer_class = ListingImageOwnerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListingImage.objects.filter(
            listing__seller=self.request.user
        ).select_related("listing")

    def perform_create(self, serializer):
        listing = serializer.validated_data["listing"]
        try:
            image = services.add_listing_image(
                listing,
                image_url=serializer.validated_data["image_url"],
                caption=serializer.validated_data.get("caption", ""),
                order=serializer.validated_data.get("order", 0),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        serializer.instance = image


class MyListingImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/marketplace/my/images/<pk>/

    Scoped to images on the authenticated user's own listings.
    IsListingImageOwner kept as an explicit second layer of defense.
    """

    serializer_class = ListingImageOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsListingImageOwner]

    def get_queryset(self):
        return ListingImage.objects.filter(
            listing__seller=self.request.user
        ).select_related("listing")


class SetPrimaryImageView(APIView):
    """POST /api/v1/marketplace/my/images/<pk>/set-primary/ — seller action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        image = get_object_or_404(
            ListingImage, pk=pk, listing__seller=request.user
        )
        services.set_primary_image(image)
        return Response(ListingImageOwnerSerializer(image).data)


class _AdminModerationActionView(APIView):
    """Shared shape for admin moderation actions; subclasses set `action`."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    action = None

    def post(self, request, pk):
        listing = get_object_or_404(MarketplaceListing, pk=pk)
        notes = request.data.get("notes", "")
        try:
            self.action(listing, notes=notes)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(MarketplaceListingOwnerSerializer(listing).data)


class ApproveListingView(_AdminModerationActionView):
    """POST /api/v1/marketplace/admin/<pk>/approve/ — admin-only."""

    action = staticmethod(services.approve_listing)


class RejectListingView(_AdminModerationActionView):
    """POST /api/v1/marketplace/admin/<pk>/reject/ — admin-only."""

    action = staticmethod(services.reject_listing)


class RequestListingChangesView(_AdminModerationActionView):
    """POST /api/v1/marketplace/admin/<pk>/request-changes/ — admin-only."""

    action = staticmethod(services.request_listing_changes)


class SuspendListingView(_AdminModerationActionView):
    """POST /api/v1/marketplace/admin/<pk>/suspend/ — admin-only."""

    action = staticmethod(services.suspend_listing)


class RestoreListingView(_AdminModerationActionView):
    """POST /api/v1/marketplace/admin/<pk>/restore/ — admin-only."""

    action = staticmethod(services.restore_listing)
