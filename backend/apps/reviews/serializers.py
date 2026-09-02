from rest_framework import serializers

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.marketplace.models import MarketplaceListing
from apps.services.models import Service

from .models import Review


class ReviewerSummarySerializer(serializers.ModelSerializer):
    """
    Minimal, public-safe reviewer identity. Deliberately excludes
    email and any other contact/account info — a public review only
    ever needs a display name, never a way to contact the reviewer.
    """

    class Meta:
        model = User
        fields = ["id", "first_name"]


class ReviewPublicSerializer(serializers.ModelSerializer):
    """
    Public representation of a review. Only ever served for reviews
    already filtered to status=PUBLISHED by the view's queryset.
    Excludes status, moderation_notes, and the target FKs — none of
    that is public-facing detail.
    """

    reviewer = ReviewerSummarySerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "reviewer", "rating", "body", "created_at"]


class ReviewOwnerSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for the review author's own view of their
    review. `reviewer` is never a field here at all — set only via
    services.create_review from request.user. The target
    (business/service/marketplace_listing) and `status` are read-only:
    a review's target never changes after creation, and status only
    changes through the dedicated admin moderation endpoints.

    `moderation_notes` IS included here (unlike the public serializer)
    so an author can see why their review was hidden — this mirrors
    BusinessOwnerSerializer exposing verification_notes to its owner;
    it is still never exposed publicly.
    """

    class Meta:
        model = Review
        fields = [
            "id",
            "business",
            "service",
            "marketplace_listing",
            "rating",
            "body",
            "status",
            "moderation_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "business",
            "service",
            "marketplace_listing",
            "status",
            "moderation_notes",
            "created_at",
            "updated_at",
        ]


class ReviewCreateSerializer(serializers.Serializer):
    """
    Input shape for creating a review. Not a ModelSerializer: only
    field-shape validation (rating range, body length, that supplied
    IDs exist) happens here. Self-review, target-eligibility, and
    duplicate checks are business rules and live in
    apps.reviews.services.create_review instead.
    """

    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), required=False, allow_null=True
    )
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), required=False, allow_null=True
    )
    marketplace_listing = serializers.PrimaryKeyRelatedField(
        queryset=MarketplaceListing.objects.all(), required=False, allow_null=True
    )
    rating = serializers.IntegerField(min_value=1, max_value=5)
    body = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ModerationActionSerializer(serializers.Serializer):
    """Request body for admin moderation-action endpoints."""

    notes = serializers.CharField(required=False, allow_blank=True, default="")
