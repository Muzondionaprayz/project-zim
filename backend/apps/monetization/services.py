"""
Monetization foundation business logic: subscription and payment
transaction lifecycle.

Isolated from views/serializers, same convention as every other
domain's services.py in this project. Audit logging uses the single
entry point introduced in Phase 10 (apps.adminpanel.services.log_action)
— this is the only cross-app import this module needs; no existing
app requires any change to support it.

No real money moves anywhere in this module. A Subscription only
ever becomes ACTIVE as a side effect of an admin marking a
PaymentTransaction COMPLETED — never from client-supplied state.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PaymentTransaction, Subscription, SubscriptionPlan

_BILLING_PERIOD_DELTAS = {
    SubscriptionPlan.BillingPeriod.MONTHLY: timedelta(days=30),
    SubscriptionPlan.BillingPeriod.YEARLY: timedelta(days=365),
}

# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


def create_subscription(user, plan: SubscriptionPlan, business=None) -> Subscription:
    """
    Creates a new PENDING subscription. If `business` is supplied,
    the subscribing user must own it — you can only buy an upgrade
    for a business that is actually yours.
    """
    if not plan.is_active:
        raise ValidationError("This plan is not currently available.")
    if business is not None and business.owner_id != user.id:
        raise ValidationError("You can only subscribe on behalf of your own business.")

    return Subscription.objects.create(user=user, plan=plan, business=business)


def activate_subscription(subscription: Subscription, actor=None) -> Subscription:
    """
    Marks a subscription active and computes its expiry from the
    plan's billing period (one-time plans never expire). Called
    automatically when a transaction is completed (see
    mark_transaction_completed), and also exposed as a direct admin
    action for manual corrections.
    """
    if subscription.status != Subscription.Status.PENDING:
        raise ValidationError("Only pending subscriptions can be activated.")

    now = timezone.now()
    subscription.status = Subscription.Status.ACTIVE
    subscription.starts_at = now
    delta = _BILLING_PERIOD_DELTAS.get(
        subscription.plan.billing_period if subscription.plan else None
    )
    subscription.ends_at = now + delta if delta else None
    subscription.save(update_fields=["status", "starts_at", "ends_at", "updated_at"])

    if actor is not None:
        _log(actor, "subscription.activated", subscription)
    return subscription


def cancel_subscription(subscription: Subscription, actor=None) -> Subscription:
    """Cancels a pending or active subscription. Callable by the owner or an admin."""
    if subscription.status not in (Subscription.Status.PENDING, Subscription.Status.ACTIVE):
        raise ValidationError("Only pending or active subscriptions can be canceled.")
    subscription.status = Subscription.Status.CANCELED
    subscription.save(update_fields=["status", "updated_at"])

    if actor is not None:
        _log(actor, "subscription.canceled", subscription)
    return subscription


def expire_subscription(subscription: Subscription, actor=None) -> Subscription:
    """Admin action: mark an active subscription expired (e.g. past its end date)."""
    if subscription.status != Subscription.Status.ACTIVE:
        raise ValidationError("Only active subscriptions can be expired.")
    subscription.status = Subscription.Status.EXPIRED
    subscription.save(update_fields=["status", "updated_at"])

    if actor is not None:
        _log(actor, "subscription.expired", subscription)
    return subscription


# ---------------------------------------------------------------------------
# Payment transactions
# ---------------------------------------------------------------------------


def record_transaction(
    subscription: Subscription,
    amount,
    currency: str = "USD",
    provider: str = PaymentTransaction.Provider.MANUAL,
    reference: str = "",
) -> PaymentTransaction:
    """
    Declares a payment against `subscription`. Anyone who can reach
    this (the subscription's own owner, in the view layer) may
    declare that a payment was made — this only ever creates a
    PENDING record; nothing is trusted or activated until an admin
    completes it.
    """
    return PaymentTransaction.objects.create(
        subscription=subscription,
        amount=amount,
        currency=currency,
        provider=provider,
        reference=reference,
    )


def mark_transaction_completed(transaction: PaymentTransaction, actor=None) -> PaymentTransaction:
    """
    Admin action: confirm a payment was received. Activates the
    associated subscription as a direct consequence — this is the
    only path by which a subscription becomes ACTIVE.
    """
    if transaction.status != PaymentTransaction.Status.PENDING:
        raise ValidationError("Only pending transactions can be completed.")
    transaction.status = PaymentTransaction.Status.COMPLETED
    transaction.save(update_fields=["status", "updated_at"])

    if transaction.subscription.status == Subscription.Status.PENDING:
        activate_subscription(transaction.subscription, actor=actor)

    if actor is not None:
        _log(actor, "transaction.completed", transaction)
    return transaction


def mark_transaction_failed(transaction: PaymentTransaction, actor=None) -> PaymentTransaction:
    """Admin action: mark a pending transaction as failed."""
    if transaction.status != PaymentTransaction.Status.PENDING:
        raise ValidationError("Only pending transactions can be marked failed.")
    transaction.status = PaymentTransaction.Status.FAILED
    transaction.save(update_fields=["status", "updated_at"])

    if actor is not None:
        _log(actor, "transaction.failed", transaction)
    return transaction


def refund_transaction(transaction: PaymentTransaction, actor=None) -> PaymentTransaction:
    """
    Admin action: mark a completed transaction as refunded. Does not
    automatically cancel the associated subscription — that remains
    a separate, deliberate admin decision.
    """
    if transaction.status != PaymentTransaction.Status.COMPLETED:
        raise ValidationError("Only completed transactions can be refunded.")
    transaction.status = PaymentTransaction.Status.REFUNDED
    transaction.save(update_fields=["status", "updated_at"])

    if actor is not None:
        _log(actor, "transaction.refunded", transaction)
    return transaction


def _log(actor, action, obj):
    from apps.adminpanel.services import log_action

    log_action(
        actor=actor,
        action=action,
        target_type=obj.__class__.__name__.lower(),
        target_id=obj.id,
    )
