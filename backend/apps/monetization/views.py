from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole

from . import services
from .models import PaymentTransaction, Subscription, SubscriptionPlan
from .permissions import IsSubscriptionOwner, IsTransactionOwner
from .serializers import (
    AdminSubscriptionSerializer,
    AdminTransactionSerializer,
    SubscriptionCreateSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    TransactionCreateSerializer,
    TransactionSerializer,
)


class SubscriptionPlanListView(generics.ListAPIView):
    """GET /api/v1/monetization/plans/ — public list of active plans."""

    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]


class MySubscriptionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/monetization/my/subscriptions/ — list the caller's own subscriptions
    POST /api/v1/monetization/my/subscriptions/ — subscribe to a plan

    `user` always comes from request.user via services.create_subscription
    — there is no writable user field anywhere in this app.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related(
            "plan", "business"
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SubscriptionCreateSerializer
        return SubscriptionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            subscription = services.create_subscription(
                user=request.user,
                plan=serializer.validated_data["plan"],
                business=serializer.validated_data.get("business"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)


class MySubscriptionDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/monetization/my/subscriptions/<pk>/

    Scoped to the caller's own subscriptions. IsSubscriptionOwner
    kept as an explicit second layer of defense.
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsSubscriptionOwner]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related(
            "plan", "business"
        )


class CancelMySubscriptionView(APIView):
    """POST /api/v1/monetization/my/subscriptions/<pk>/cancel/ — owner action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        subscription = get_object_or_404(Subscription, pk=pk, user=request.user)
        try:
            services.cancel_subscription(subscription, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(SubscriptionSerializer(subscription).data)


class MyTransactionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/monetization/my/subscriptions/<pk>/transactions/ — list
    POST /api/v1/monetization/my/subscriptions/<pk>/transactions/ — declare a payment

    Scoped to one of the caller's own subscriptions; a subscription
    ID that isn't theirs 404s before any transaction read/write is
    attempted. Declaring a transaction only ever creates a PENDING
    record — see services.record_transaction.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_subscription(self):
        return get_object_or_404(
            Subscription, pk=self.kwargs["pk"], user=self.request.user
        )

    def get_queryset(self):
        return self.get_subscription().transactions.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TransactionCreateSerializer
        return TransactionSerializer

    def create(self, request, *args, **kwargs):
        subscription = self.get_subscription()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = services.record_transaction(
            subscription=subscription,
            amount=serializer.validated_data["amount"],
            currency=serializer.validated_data.get("currency", "USD"),
            provider=serializer.validated_data.get("provider", PaymentTransaction.Provider.MANUAL),
            reference=serializer.validated_data.get("reference", ""),
        )
        return Response(TransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Admin: cross-user visibility and lifecycle actions
# ---------------------------------------------------------------------------


class AdminSubscriptionListView(generics.ListAPIView):
    """GET /api/v1/monetization/admin/subscriptions/ — all subscriptions, admin-only."""

    serializer_class = AdminSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = Subscription.objects.all().select_related("user", "plan", "business")
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


class AdminActivateSubscriptionView(APIView):
    """POST /api/v1/monetization/admin/subscriptions/<pk>/activate/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        subscription = get_object_or_404(Subscription, pk=pk)
        try:
            services.activate_subscription(subscription, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminSubscriptionSerializer(subscription).data)


class AdminCancelSubscriptionView(APIView):
    """POST /api/v1/monetization/admin/subscriptions/<pk>/cancel/ — admin-only forced cancel."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        subscription = get_object_or_404(Subscription, pk=pk)
        try:
            services.cancel_subscription(subscription, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminSubscriptionSerializer(subscription).data)


class AdminExpireSubscriptionView(APIView):
    """POST /api/v1/monetization/admin/subscriptions/<pk>/expire/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        subscription = get_object_or_404(Subscription, pk=pk)
        try:
            services.expire_subscription(subscription, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminSubscriptionSerializer(subscription).data)


class AdminTransactionListView(generics.ListAPIView):
    """GET /api/v1/monetization/admin/transactions/ — all transactions, admin-only."""

    serializer_class = AdminTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = PaymentTransaction.objects.all().select_related("subscription__user")
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


class AdminCompleteTransactionView(APIView):
    """
    POST /api/v1/monetization/admin/transactions/<pk>/complete/ — admin-only.

    Also activates the associated subscription — see
    services.mark_transaction_completed.
    """

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        transaction = get_object_or_404(PaymentTransaction, pk=pk)
        try:
            services.mark_transaction_completed(transaction, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminTransactionSerializer(transaction).data)


class AdminFailTransactionView(APIView):
    """POST /api/v1/monetization/admin/transactions/<pk>/fail/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        transaction = get_object_or_404(PaymentTransaction, pk=pk)
        try:
            services.mark_transaction_failed(transaction, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminTransactionSerializer(transaction).data)


class AdminRefundTransactionView(APIView):
    """POST /api/v1/monetization/admin/transactions/<pk>/refund/ — admin-only."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        transaction = get_object_or_404(PaymentTransaction, pk=pk)
        try:
            services.refund_transaction(transaction, actor=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(AdminTransactionSerializer(transaction).data)
