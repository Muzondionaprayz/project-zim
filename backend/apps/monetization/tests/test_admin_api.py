from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.monetization.models import PaymentTransaction, Subscription, SubscriptionPlan


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class AdminSubscriptionListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.pending_sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.active_sub = Subscription.objects.create(
            user=self.user, plan=self.plan, status=Subscription.Status.ACTIVE
        )
        self.url = reverse("monetization:admin-subscription-list")

    def test_admin_sees_all_subscriptions(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {self.pending_sub.id, self.active_sub.id})

    def test_ordinary_user_cannot_access(self):
        self.authenticate_as(self.ordinary_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"status": "active"})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.active_sub.id])

    def test_admin_list_includes_user_email(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        item = next(i for i in response.data["results"] if i["id"] == self.pending_sub.id)
        self.assertEqual(item["user_email"], "user@example.com")


class AdminSubscriptionActionAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)

    def test_admin_can_activate_subscription(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-subscription-activate", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.ACTIVE)

    def test_ordinary_user_cannot_activate_subscription(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("monetization:admin-subscription-activate", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_subscription_owner_cannot_use_admin_activate_endpoint(self):
        self.authenticate_as(self.user)
        url = reverse("monetization:admin-subscription-activate", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_force_cancel_subscription(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-subscription-cancel", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.CANCELED)

    def test_admin_can_expire_active_subscription(self):
        self.sub.status = Subscription.Status.ACTIVE
        self.sub.save()
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-subscription-expire", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.EXPIRED)

    def test_invalid_transition_returns_400_not_500(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-subscription-expire", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)  # still PENDING, cannot expire
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_activate(self):
        url = reverse("monetization:admin-subscription-activate", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminTransactionListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.txn = PaymentTransaction.objects.create(subscription=self.sub, amount=Decimal("5.00"))
        self.url = reverse("monetization:admin-transaction-list")

    def test_admin_sees_all_transactions(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.txn.id])

    def test_ordinary_user_cannot_access(self):
        self.authenticate_as(self.ordinary_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_list_includes_user_email(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.data["results"][0]["user_email"], "user@example.com")


class AdminTransactionActionAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.txn = PaymentTransaction.objects.create(subscription=self.sub, amount=Decimal("5.00"))

    def test_admin_can_complete_transaction(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-transaction-complete", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, PaymentTransaction.Status.COMPLETED)

    def test_completing_transaction_activates_subscription(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-transaction-complete", kwargs={"pk": self.txn.pk})
        self.client.post(url)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.ACTIVE)

    def test_ordinary_user_cannot_complete_transaction(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("monetization:admin-transaction-complete", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_subscription_owner_cannot_complete_own_transaction(self):
        """
        Even the person who declared the payment cannot confirm it
        themselves — completion is an admin-only trust boundary.
        """
        self.authenticate_as(self.user)
        url = reverse("monetization:admin-transaction-complete", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_fail_transaction(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-transaction-fail", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, PaymentTransaction.Status.FAILED)

    def test_ordinary_user_cannot_fail_transaction(self):
        self.authenticate_as(self.ordinary_user)
        url = reverse("monetization:admin-transaction-fail", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_refund_completed_transaction(self):
        self.txn.status = PaymentTransaction.Status.COMPLETED
        self.txn.save()
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-transaction-refund", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, PaymentTransaction.Status.REFUNDED)

    def test_ordinary_user_cannot_refund_transaction(self):
        self.txn.status = PaymentTransaction.Status.COMPLETED
        self.txn.save()
        self.authenticate_as(self.ordinary_user)
        url = reverse("monetization:admin-transaction-refund", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_transition_returns_400_not_500(self):
        self.authenticate_as(self.admin)
        url = reverse("monetization:admin-transaction-refund", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)  # still PENDING, cannot refund
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_complete(self):
        url = reverse("monetization:admin-transaction-complete", kwargs={"pk": self.txn.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
