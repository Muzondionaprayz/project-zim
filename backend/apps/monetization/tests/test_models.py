from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.monetization.models import PaymentTransaction, Subscription, SubscriptionPlan


class SubscriptionPlanModelTests(TestCase):
    def test_slug_auto_generated(self):
        plan = SubscriptionPlan.objects.create(name="Featured Listing Monthly", price=Decimal("9.99"))
        self.assertEqual(plan.slug, "featured-listing-monthly")

    def test_defaults(self):
        plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.currency, "USD")
        self.assertEqual(plan.billing_period, SubscriptionPlan.BillingPeriod.MONTHLY)

    def test_negative_price_fails_validation(self):
        plan = SubscriptionPlan(name="Bad Plan", price=Decimal("-1"))
        with self.assertRaises(ValidationError):
            plan.full_clean()

    def test_str_returns_name(self):
        plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.assertEqual(str(plan), "Plan")


class SubscriptionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))

    def test_defaults_to_pending(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.assertEqual(sub.status, Subscription.Status.PENDING)

    def test_is_active_subscription_false_when_pending(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.assertFalse(sub.is_active_subscription)

    def test_is_active_subscription_true_when_active(self):
        sub = Subscription.objects.create(
            user=self.user, plan=self.plan, status=Subscription.Status.ACTIVE
        )
        self.assertTrue(sub.is_active_subscription)

    def test_deleting_plan_sets_null_not_cascade(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.plan.delete()
        sub.refresh_from_db()
        self.assertIsNone(sub.plan)

    def test_deleting_user_deletes_subscription(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        sub_id = sub.id
        self.user.delete()
        self.assertFalse(Subscription.objects.filter(id=sub_id).exists())

    def test_deleting_business_sets_null_not_cascade(self):
        business = Business.objects.create(owner=self.user, name="Biz")
        sub = Subscription.objects.create(user=self.user, plan=self.plan, business=business)
        business.delete()
        sub.refresh_from_db()
        self.assertIsNone(sub.business)

    def test_str_representation(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.assertIn(str(sub.pk), str(sub))


class PaymentTransactionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.subscription = Subscription.objects.create(user=self.user, plan=self.plan)

    def test_defaults(self):
        txn = PaymentTransaction.objects.create(subscription=self.subscription, amount=Decimal("5.00"))
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(txn.provider, PaymentTransaction.Provider.MANUAL)
        self.assertEqual(txn.currency, "USD")

    def test_negative_amount_fails_validation(self):
        txn = PaymentTransaction(subscription=self.subscription, amount=Decimal("-5.00"))
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_deleting_subscription_deletes_transaction(self):
        txn = PaymentTransaction.objects.create(subscription=self.subscription, amount=Decimal("5.00"))
        txn_id = txn.id
        self.subscription.delete()
        self.assertFalse(PaymentTransaction.objects.filter(id=txn_id).exists())

    def test_str_representation(self):
        txn = PaymentTransaction.objects.create(subscription=self.subscription, amount=Decimal("5.00"))
        self.assertIn("5.00", str(txn))
