from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.monetization.models import PaymentTransaction, Subscription, SubscriptionPlan
from apps.monetization.permissions import IsSubscriptionOwner, IsTransactionOwner


class IsSubscriptionOwnerPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.permission = IsSubscriptionOwner()

    def test_allows_owner(self):
        request = Mock(user=self.user)
        self.assertTrue(self.permission.has_object_permission(request, None, self.sub))

    def test_denies_non_owner(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.sub))


class IsTransactionOwnerPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.txn = PaymentTransaction.objects.create(subscription=self.sub, amount=Decimal("5.00"))
        self.permission = IsTransactionOwner()

    def test_allows_subscription_owner(self):
        request = Mock(user=self.user)
        self.assertTrue(self.permission.has_object_permission(request, None, self.txn))

    def test_denies_non_owner(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.txn))
