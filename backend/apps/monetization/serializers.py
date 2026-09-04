from rest_framework import serializers

from apps.businesses.models import Business

from .models import PaymentTransaction, Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["id", "name", "slug", "description", "price", "currency", "billing_period"]


class SubscriptionCreateSerializer(serializers.Serializer):
    """
    Input shape for creating a subscription. Not a ModelSerializer:
    `user` is never a field (set only from request.user in the view),
    and business-ownership validation is a business rule that lives
    in services.create_subscription, not here.
    """

    plan = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True)
    )
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), required=False, allow_null=True
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Read representation of a subscription for its own owner.
    `plan`/`business`/`status` are read-only: the target and status
    never change via this serializer — only via the dedicated
    create/cancel/activate endpoints.
    """

    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "business",
            "status",
            "starts_at",
            "ends_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TransactionCreateSerializer(serializers.Serializer):
    """Input shape for declaring a payment against one of the caller's own subscriptions."""

    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    currency = serializers.CharField(max_length=3, required=False, default="USD")
    provider = serializers.ChoiceField(
        choices=PaymentTransaction.Provider.choices, required=False,
        default=PaymentTransaction.Provider.MANUAL,
    )
    reference = serializers.CharField(required=False, allow_blank=True, max_length=255)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "subscription",
            "provider",
            "reference",
            "amount",
            "currency",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "subscription", "status", "notes", "created_at", "updated_at"]


class AdminSubscriptionSerializer(SubscriptionSerializer):
    """Reuses SubscriptionSerializer as-is and adds the subscriber's email for admin visibility."""

    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + ["user_email"]
        read_only_fields = fields


class AdminTransactionSerializer(TransactionSerializer):
    user_email = serializers.EmailField(source="subscription.user.email", read_only=True)

    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + ["user_email"]
        read_only_fields = fields
