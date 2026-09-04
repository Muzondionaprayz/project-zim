from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class SubscriptionPlan(models.Model):
    """
    A purchasable plan (e.g. "Featured Business Listing — Monthly").
    Mirrors the BusinessCategory/ServiceCategory/etc. pattern: managed
    via the Django admin, public read-only list via the API.
    """

    class BillingPeriod(models.TextChoices):
        MONTHLY = "monthly", _("Monthly")
        YEARLY = "yearly", _("Yearly")
        ONE_TIME = "one_time", _("One-time")

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="USD")
    billing_period = models.CharField(
        max_length=10, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("subscription plan")
        verbose_name_plural = _("subscription plans")
        ordering = ["price"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Subscription(models.Model):
    """
    A User's (optionally Business-scoped) subscription to a Plan.

    `plan`/`business` are nullable SET_NULL FKs, the same convention
    every category-style FK in this project already uses (e.g.
    Business.category) — deleting a plan or business should never
    delete subscription history.

    No real money moves here — creating a Subscription only ever
    produces status=PENDING. It becomes ACTIVE only once an admin
    marks an associated PaymentTransaction as completed (see
    apps.monetization.services), which is the intentional trust
    boundary: nothing self-reported activates a subscription.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending Payment")
        ACTIVE = "active", _("Active")
        CANCELED = "canceled", _("Canceled")
        EXPIRED = "expired", _("Expired")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions"
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Subscription<{self.pk}> ({self.user})"

    @property
    def is_active_subscription(self):
        return self.status == self.Status.ACTIVE


class PaymentTransaction(models.Model):
    """
    A single payment event against a Subscription.

    `provider` is a TextChoices with one real member (MANUAL) —
    admin manually records that a payment was received, with no
    gateway integration. Adding a real provider later (Stripe,
    EcoCash, etc.) means adding a new TextChoices member and a
    webhook view that calls the existing service functions — no
    change to this model's shape.

    Only an admin may move a transaction out of PENDING (see
    apps.monetization.services) — the subscriber may declare that
    they paid, but nothing here trusts that claim until an admin
    confirms it.
    """

    class Provider(models.TextChoices):
        MANUAL = "manual", _("Manual / Offline")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="transactions"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.MANUAL)
    reference = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("payment transaction")
        verbose_name_plural = _("payment transactions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Transaction<{self.pk}> {self.amount} {self.currency} ({self.status})"
