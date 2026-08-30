from rest_framework import serializers

from apps.businesses.models import Business
from apps.businesses.serializers import BusinessPublicListSerializer

from .models import Service, ServiceCategory


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ["id", "name", "slug", "description"]


class ServicePublicListSerializer(serializers.ModelSerializer):
    """
    Used for the public catalog list. Reuses BusinessPublicListSerializer
    for the nested business summary so business-side sensitive fields
    (owner, verification_notes, etc.) are excluded the same way here
    as they are on the businesses endpoints themselves — one place
    defines "safe to show publicly" for a business.
    """

    category = ServiceCategorySerializer(read_only=True)
    business = BusinessPublicListSerializer(read_only=True)

    class Meta:
        model = Service
        fields = ["id", "title", "slug", "category", "price", "price_type", "business"]


class ServicePublicDetailSerializer(serializers.ModelSerializer):
    """
    Used for public service detail. Only ever served for services
    already filtered to is_active=True AND business status=APPROVED
    by the view's queryset.

    Intentionally excludes: is_active (internal publish flag) and
    anything about the business beyond its own public summary.
    """

    category = ServiceCategorySerializer(read_only=True)
    business = BusinessPublicListSerializer(read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "price",
            "price_type",
            "duration_minutes",
            "business",
            "created_at",
            "updated_at",
        ]


class ServiceOwnerSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for a business owner's own service.

    `business` is writable, but its queryset is restricted to the
    requesting user's own businesses (set in __init__ from
    context["request"]). This means a client cannot create or move a
    service onto a business they don't own even by guessing a valid
    business ID — DRF rejects it as "does not exist" before it ever
    reaches the view, the same class of protection Business gets by
    having no writable `owner` field at all.

    `is_active` is read-only here: publishing/unpublishing goes
    through the dedicated activate/deactivate endpoints so the
    "business must be approved to activate" rule (see services.py)
    is enforced in exactly one place.
    """

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=ServiceCategory.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "business",
            "title",
            "slug",
            "description",
            "category",
            "price",
            "price_type",
            "duration_minutes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "is_active", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and "business" in self.fields:
            self.fields["business"].queryset = Business.objects.filter(
                owner=request.user
            )
