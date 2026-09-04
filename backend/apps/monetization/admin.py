from django.contrib import admin

from .models import PaymentTransaction, Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "price", "currency", "billing_period", "is_active"]
    list_filter = ["is_active", "billing_period"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class TransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    readonly_fields = ["status", "created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """
    Read-mostly admin view. Status transitions should go through
    apps.monetization.services (and the dedicated API actions) so
    transition rules stay enforced in one place.
    """

    list_display = ["id", "user", "plan", "business", "status", "starts_at", "ends_at"]
    list_filter = ["status"]
    search_fields = ["user__email"]
    readonly_fields = ["status", "starts_at", "ends_at", "created_at", "updated_at"]
    inlines = [TransactionInline]


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "subscription", "provider", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "provider"]
    search_fields = ["subscription__user__email", "reference"]
    readonly_fields = ["status", "created_at", "updated_at"]
