from rest_framework import serializers

from apps.accounts.models import User
from apps.businesses.serializers import BusinessOwnerSerializer
from apps.marketplace.serializers import MarketplaceListingOwnerSerializer
from apps.reviews.serializers import ReviewOwnerSerializer

from .models import AuditLog


class AdminUserSerializer(serializers.ModelSerializer):
    """
    Admin-facing user representation. Read-only here: role and
    is_active changes go through the dedicated action endpoints
    (change_user_role/activate_user/deactivate_user), the same
    "status changes only via actions" convention used everywhere
    else in this project.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "is_staff",
            "date_joined",
        ]
        read_only_fields = fields


class ChangeUserRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class AdminBusinessSerializer(BusinessOwnerSerializer):
    """
    Reuses BusinessOwnerSerializer as-is (same fields an owner sees,
    including verification_notes) and only adds the owner's email so
    an admin can identify whose business this is — no duplication of
    the underlying field list.
    """

    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta(BusinessOwnerSerializer.Meta):
        fields = BusinessOwnerSerializer.Meta.fields + ["owner_email"]


class AdminMarketplaceListingSerializer(MarketplaceListingOwnerSerializer):
    seller_email = serializers.EmailField(source="seller.email", read_only=True)

    class Meta(MarketplaceListingOwnerSerializer.Meta):
        fields = MarketplaceListingOwnerSerializer.Meta.fields + ["seller_email"]


class AdminReviewSerializer(ReviewOwnerSerializer):
    reviewer_email = serializers.EmailField(source="reviewer.email", read_only=True)

    class Meta(ReviewOwnerSerializer.Meta):
        fields = ReviewOwnerSerializer.Meta.fields + ["reviewer_email"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "details",
            "created_at",
        ]
        read_only_fields = fields
