from rest_framework import serializers

from .models import ListingImage, MarketplaceCategory, MarketplaceListing


class MarketplaceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceCategory
        fields = ["id", "name", "slug", "description"]


class ListingImagePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image_url", "caption", "order", "is_primary"]


class MarketplaceListingPublicListSerializer(serializers.ModelSerializer):
    """
    Public catalog list. Excludes `seller`, `moderation_status`,
    `moderation_notes` — mirrors Business's exclusion of owner and
    verification internals.
    """

    category = MarketplaceCategorySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = MarketplaceListing
        fields = [
            "id",
            "title",
            "slug",
            "category",
            "price",
            "price_type",
            "condition",
            "city",
            "province",
            "primary_image",
        ]

    def get_primary_image(self, obj):
        image = next((img for img in obj.images.all() if img.is_primary), None)
        return ListingImagePublicSerializer(image).data if image else None


class MarketplaceListingPublicDetailSerializer(serializers.ModelSerializer):
    """
    Public detail. Only ever served for listings already filtered to
    status=PUBLISHED and moderation_status=APPROVED by the view.
    Excludes seller and moderation internals.
    """

    category = MarketplaceCategorySerializer(read_only=True)
    images = ListingImagePublicSerializer(many=True, read_only=True)

    class Meta:
        model = MarketplaceListing
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "price",
            "price_type",
            "condition",
            "city",
            "province",
            "address",
            "phone",
            "whatsapp",
            "email",
            "images",
            "created_at",
            "updated_at",
        ]


class MarketplaceListingOwnerSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for a seller's own listing.

    `seller` is deliberately not a field here at all — set only in
    the view's perform_create from request.user. `status` and
    `moderation_status`/`moderation_notes` are read-only: transitions
    only happen through the dedicated publish/unpublish and admin
    moderation endpoints (see services.py).
    """

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=MarketplaceCategory.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    images = ListingImagePublicSerializer(many=True, read_only=True)

    class Meta:
        model = MarketplaceListing
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "price",
            "price_type",
            "condition",
            "city",
            "province",
            "address",
            "phone",
            "whatsapp",
            "email",
            "status",
            "moderation_status",
            "moderation_notes",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "status",
            "moderation_status",
            "moderation_notes",
            "created_at",
            "updated_at",
        ]


class ListingImageOwnerSerializer(serializers.ModelSerializer):
    """
    Used by a seller to manage images on their own listings.

    `listing`'s queryset is restricted to the requesting user's own
    listings (set in __init__ from context["request"]), the same
    protection Service.business gets — a client cannot attach an
    image to a listing they don't own even by guessing a valid ID.
    `is_primary` is read-only here; changing which image is primary
    goes through the dedicated set-primary action.
    """

    class Meta:
        model = ListingImage
        fields = ["id", "listing", "image_url", "caption", "order", "is_primary", "created_at"]
        read_only_fields = ["id", "is_primary", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and "listing" in self.fields:
            self.fields["listing"].queryset = MarketplaceListing.objects.filter(
                seller=request.user
            )
