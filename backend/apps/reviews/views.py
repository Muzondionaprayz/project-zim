from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole

from . import services
from .models import Review
from .permissions import IsReviewOwner
from .serializers import (
    ModerationActionSerializer,
    ReviewCreateSerializer,
    ReviewOwnerSerializer,
    ReviewPublicSerializer,
)


def _public_queryset():
    return Review.objects.filter(status=Review.Status.PUBLISHED).select_related("reviewer")


class PublicReviewListView(generics.ListAPIView):
    """
    GET /api/v1/reviews/

    Public list of reviews. Hard-filtered to status=PUBLISHED
    regardless of any query parameter — hidden reviews are never
    reachable here. Filterable by exactly one target via `business`,
    `service`, or `marketplace_listing` query params (each an ID).
    """

    serializer_class = ReviewPublicSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = _public_queryset()
        params = self.request.query_params
        if params.get("business"):
            queryset = queryset.filter(business_id=params["business"])
        if params.get("service"):
            queryset = queryset.filter(service_id=params["service"])
        if params.get("marketplace_listing"):
            queryset = queryset.filter(marketplace_listing_id=params["marketplace_listing"])
        return queryset


class PublicReviewDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/reviews/<pk>/

    Uses the same PUBLISHED-only queryset as the list endpoint, so a
    hidden review 404s rather than leaking its existence or data.
    """

    serializer_class = ReviewPublicSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return _public_queryset()


class MyReviewListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/reviews/my/ — list the authenticated user's own reviews
    POST /api/v1/reviews/my/ — create a new review

    `reviewer` always comes from request.user via
    services.create_review — there is no writable reviewer field
    anywhere in this app.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(reviewer=self.request.user).select_related(
            "business", "service", "marketplace_listing"
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ReviewCreateSerializer
        return ReviewOwnerSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = services.create_review(
                reviewer=request.user,
                business=serializer.validated_data.get("business"),
                service=serializer.validated_data.get("service"),
                marketplace_listing=serializer.validated_data.get("marketplace_listing"),
                rating=serializer.validated_data["rating"],
                body=serializer.validated_data.get("body", ""),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        output = ReviewOwnerSerializer(review)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MyReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/reviews/my/<pk>/

    Scoped to the authenticated user's own reviews. IsReviewOwner
    kept as an explicit second layer of defense. Only `rating`/`body`
    are writable (see ReviewOwnerSerializer read_only_fields).
    """

    serializer_class = ReviewOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsReviewOwner]

    def get_queryset(self):
        return Review.objects.filter(reviewer=self.request.user).select_related(
            "business", "service", "marketplace_listing"
        )


class _ReviewModerationActionView(APIView):
    """Shared shape for admin moderation-action endpoints; subclasses set `action`."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    action = None

    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        serializer = ModerationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.action(review, notes=serializer.validated_data.get("notes", ""))
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(ReviewOwnerSerializer(review).data)


class HideReviewView(_ReviewModerationActionView):
    """POST /api/v1/reviews/admin/<pk>/hide/ — admin-only."""

    action = staticmethod(services.hide_review)


class RestoreReviewView(_ReviewModerationActionView):
    """POST /api/v1/reviews/admin/<pk>/restore/ — admin-only."""

    action = staticmethod(services.restore_review)
