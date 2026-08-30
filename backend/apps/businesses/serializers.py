from rest_framework import serializers

from .models import Business, BusinessCategory


class BusinessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = ["id", "name", "slug", "description"]


class BusinessPublicListSerializer(serializers.ModelSerializer):
    """
    Used for the public catalog list. Deliberately lightweight —
    excludes description/address/opening_hours/verification detail
    to keep list responses small; full detail is a separate request.
    """

    category = BusinessCategorySerializer(read_only=True)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "city",
            "province",
            "logo_url",
            "phone",
            "whatsapp",
        ]


class BusinessPublicDetailSerializer(serializers.ModelSerializer):
    """
    Used for public business detail. Only ever served for businesses
    already filtered to status=APPROVED by the view's queryset.

    Intentionally excludes: owner, verification_notes, submitted_at,
    verified_at — internal/administrative fields with no place in a
    public response.
    """

    category = BusinessCategorySerializer(read_only=True)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "phone",
            "whatsapp",
            "email",
            "address",
            "city",
            "province",
            "latitude",
            "longitude",
            "logo_url",
            "cover_image_url",
            "opening_hours",
            "status",
            "created_at",
            "updated_at",
        ]


class BusinessOwnerSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for a business owner's own listing.

    `owner` is deliberately not a field here at all — it is set only
    in the view's perform_create from request.user, so there is no
    field for a client to spoof even if they include "owner" in the
    request body (DRF silently ignores unknown input keys).

    `status`, `verification_notes`, `submitted_at`, and `verified_at`
    are read-only: the owner can see where their listing stands in
    the verification lifecycle, but transitions only happen through
    the dedicated submit/admin-action endpoints (see services.py).
    """

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=BusinessCategory.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "phone",
            "whatsapp",
            "email",
            "address",
            "city",
            "province",
            "latitude",
            "longitude",
            "logo_url",
            "cover_image_url",
            "opening_hours",
            "status",
            "verification_notes",
            "submitted_at",
            "verified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "status",
            "verification_notes",
            "submitted_at",
            "verified_at",
            "created_at",
            "updated_at",
        ]


class VerificationActionSerializer(serializers.Serializer):
    """Request body for admin verification-action endpoints."""

    notes = serializers.CharField(required=False, allow_blank=True, default="")
