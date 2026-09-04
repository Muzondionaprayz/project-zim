from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.adminpanel.models import AuditLog
from apps.businesses.models import Business
from apps.monetization import services
from apps.monetization.models import PaymentTransaction, Subscription, SubscriptionPlan


class CreateSubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.inactive_plan = SubscriptionPlan.objects.create(
            name="Inactive Plan", price=Decimal("5.00"), is_active=False
        )
        self.business = Business.objects.create(owner=self.user, name="Biz")

    def test_create_subscription_without_business(self):
        sub = services.create_subscription(self.user, self.plan)
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.status, Subscription.Status.PENDING)

    def test_create_subscription_with_own_business(self):
        sub = services.create_subscription(self.user, self.plan, business=self.business)
        self.assertEqual(sub.business, self.business)

    def test_cannot_subscribe_on_behalf_of_someone_elses_business(self):
        with self.assertRaises(ValidationError):
            services.create_subscription(self.other_user, self.plan, business=self.business)

    def test_cannot_subscribe_to_inactive_plan(self):
        with self.assertRaises(ValidationError):
            services.create_subscription(self.user, self.inactive_plan)


class ActivateSubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.monthly_plan = SubscriptionPlan.objects.create(
            name="Monthly", price=Decimal("5.00"), billing_period=SubscriptionPlan.BillingPeriod.MONTHLY
        )
        self.one_time_plan = SubscriptionPlan.objects.create(
            name="OneTime", price=Decimal("5.00"), billing_period=SubscriptionPlan.BillingPeriod.ONE_TIME
        )

    def test_activate_pending_subscription(self):
        sub = Subscription.objects.create(user=self.user, plan=self.monthly_plan)
        services.activate_subscription(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertIsNotNone(sub.starts_at)
        self.assertIsNotNone(sub.ends_at)

    def test_activate_one_time_plan_has_no_expiry(self):
        sub = Subscription.objects.create(user=self.user, plan=self.one_time_plan)
        services.activate_subscription(sub)
        sub.refresh_from_db()
        self.assertIsNone(sub.ends_at)

    def test_activate_non_pending_is_rejected(self):
        sub = Subscription.objects.create(
            user=self.user, plan=self.monthly_plan, status=Subscription.Status.ACTIVE
        )
        with self.assertRaises(ValidationError):
            services.activate_subscription(sub)

    def test_activate_logs_action_when_actor_given(self):
        sub = Subscription.objects.create(user=self.user, plan=self.monthly_plan)
        services.activate_subscription(sub, actor=self.admin)
        self.assertTrue(
            AuditLog.objects.filter(actor=self.admin, action="subscription.activated").exists()
        )

    def test_activate_does_not_log_when_no_actor(self):
        sub = Subscription.objects.create(user=self.user, plan=self.monthly_plan)
        services.activate_subscription(sub)
        self.assertFalse(AuditLog.objects.filter(action="subscription.activated").exists())


class CancelExpireSubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))

    def test_cancel_pending_subscription(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        services.cancel_subscription(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.CANCELED)

    def test_cancel_active_subscription(self):
        sub = Subscription.objects.create(
            user=self.user, plan=self.plan, status=Subscription.Status.ACTIVE
        )
        services.cancel_subscription(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.CANCELED)

    def test_cancel_already_canceled_is_rejected(self):
        sub = Subscription.objects.create(
            user=self.user, plan=self.plan, status=Subscription.Status.CANCELED
        )
        with self.assertRaises(ValidationError):
            services.cancel_subscription(sub)

    def test_expire_active_subscription(self):
        sub = Subscription.objects.create(
            user=self.user, plan=self.plan, status=Subscription.Status.ACTIVE
        )
        services.expire_subscription(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.EXPIRED)

    def test_expire_pending_subscription_is_rejected(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        with self.assertRaises(ValidationError):
            services.expire_subscription(sub)


class TransactionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.subscription = Subscription.objects.create(user=self.user, plan=self.plan)

    def test_record_transaction_creates_pending(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)

    def test_complete_transaction_activates_pending_subscription(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_completed(txn, actor=self.admin)
        txn.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.Status.COMPLETED)
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)

    def test_complete_transaction_logs_action(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_completed(txn, actor=self.admin)
        self.assertTrue(
            AuditLog.objects.filter(actor=self.admin, action="transaction.completed").exists()
        )

    def test_complete_non_pending_transaction_is_rejected(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_completed(txn)
        with self.assertRaises(ValidationError):
            services.mark_transaction_completed(txn)

    def test_fail_pending_transaction(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_failed(txn, actor=self.admin)
        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)

    def test_failing_transaction_does_not_activate_subscription(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_failed(txn)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.PENDING)

    def test_fail_non_pending_transaction_is_rejected(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_completed(txn)
        with self.assertRaises(ValidationError):
            services.mark_transaction_failed(txn)

    def test_refund_completed_transaction(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_completed(txn)
        services.refund_transaction(txn, actor=self.admin)
        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.Status.REFUNDED)

    def test_refund_does_not_auto_cancel_subscription(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        services.mark_transaction_completed(txn)
        services.refund_transaction(txn)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)

    def test_refund_pending_transaction_is_rejected(self):
        txn = services.record_transaction(self.subscription, amount=Decimal("5.00"))
        with self.assertRaises(ValidationError):
            services.refund_transaction(txn)
