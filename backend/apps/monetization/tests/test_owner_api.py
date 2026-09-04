from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.monetization.models import PaymentTransaction, Subscription, SubscriptionPlan


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class SubscriptionPlanListAPITests(APITestCase):
    def test_plan_list_is_public(self):
        SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        url = reverse("monetization:plan-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_inactive_plans_excluded(self):
        SubscriptionPlan.objects.create(name="Active", price=Decimal("5.00"), is_active=True)
        SubscriptionPlan.objects.create(name="Inactive", price=Decimal("5.00"), is_active=False)
        url = reverse("monetization:plan-list")
        response = self.client.get(url)
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Active"])


class CreateSubscriptionAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.business = Business.objects.create(owner=self.user, name="Biz")
        self.others_business = Business.objects.create(owner=self.other_user, name="Their Biz")
        self.url = reverse("monetization:my-subscription-list")

    def test_unauthenticated_cannot_create_subscription(self):
        response = self.client.post(self.url, {"plan": self.plan.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_subscribe(self):
        self.authenticate_as(self.user)
        response = self.client.post(self.url, {"plan": self.plan.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_subscription_user_is_derived_from_request_user(self):
        self.authenticate_as(self.user)
        response = self.client.post(self.url, {"plan": self.plan.id})
        sub = Subscription.objects.get(id=response.data["id"])
        self.assertEqual(sub.user, self.user)

    def test_client_cannot_spoof_user_field(self):
        self.authenticate_as(self.user)
        response = self.client.post(
            self.url, {"plan": self.plan.id, "user": self.other_user.id}
        )
        sub = Subscription.objects.get(id=response.data["id"])
        self.assertEqual(sub.user, self.user)
        self.assertNotEqual(sub.user, self.other_user)

    def test_can_subscribe_with_own_business(self):
        self.authenticate_as(self.user)
        response = self.client.post(
            self.url, {"plan": self.plan.id, "business": self.business.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["business"], self.business.id)

    def test_cannot_subscribe_with_someone_elses_business(self):
        self.authenticate_as(self.user)
        response = self.client.post(
            self.url, {"plan": self.plan.id, "business": self.others_business.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_created_subscription_defaults_to_pending(self):
        self.authenticate_as(self.user)
        response = self.client.post(self.url, {"plan": self.plan.id})
        self.assertEqual(response.data["status"], Subscription.Status.PENDING)

    def test_client_cannot_set_status_at_creation(self):
        self.authenticate_as(self.user)
        response = self.client.post(
            self.url, {"plan": self.plan.id, "status": "active"}
        )
        self.assertEqual(response.data["status"], Subscription.Status.PENDING)

    def test_inactive_plan_returns_400(self):
        inactive_plan = SubscriptionPlan.objects.create(
            name="Inactive", price=Decimal("5.00"), is_active=False
        )
        self.authenticate_as(self.user)
        response = self.client.post(self.url, {"plan": inactive_plan.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MySubscriptionListDetailAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.own_sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.others_sub = Subscription.objects.create(user=self.other_user, plan=self.plan)

    def test_list_only_returns_own_subscriptions(self):
        self.authenticate_as(self.user)
        url = reverse("monetization:my-subscription-list")
        response = self.client.get(url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.own_sub.id])

    def test_cannot_view_another_users_subscription(self):
        self.authenticate_as(self.user)
        url = reverse("monetization:my-subscription-detail", kwargs={"pk": self.others_sub.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_list(self):
        url = reverse("monetization:my-subscription-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CancelMySubscriptionAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)

    def test_owner_can_cancel_own_subscription(self):
        self.authenticate_as(self.user)
        url = reverse("monetization:my-subscription-cancel", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.CANCELED)

    def test_cannot_cancel_another_users_subscription(self):
        self.authenticate_as(self.other_user)
        url = reverse("monetization:my-subscription-cancel", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.PENDING)

    def test_unauthenticated_cannot_cancel(self):
        url = reverse("monetization:my-subscription-cancel", kwargs={"pk": self.sub.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyTransactionAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.plan = SubscriptionPlan.objects.create(name="Plan", price=Decimal("5.00"))
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan)
        self.others_sub = Subscription.objects.create(user=self.other_user, plan=self.plan)
        self.url = reverse("monetization:my-transaction-list", kwargs={"pk": self.sub.pk})

    def test_unauthenticated_cannot_declare_transaction(self):
        response = self.client.post(self.url, {"amount": "5.00"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_declare_transaction(self):
        self.authenticate_as(self.user)
        response = self.client.post(self.url, {"amount": "5.00", "reference": "EC12345"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], PaymentTransaction.Status.PENDING)

    def test_cannot_declare_transaction_against_another_users_subscription(self):
        self.authenticate_as(self.user)
        others_url = reverse(
            "monetization:my-transaction-list", kwargs={"pk": self.others_sub.pk}
        )
        response = self.client.post(others_url, {"amount": "5.00"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_cannot_set_status_at_creation(self):
        self.authenticate_as(self.user)
        response = self.client.post(
            self.url, {"amount": "5.00", "status": "completed"}
        )
        self.assertEqual(response.data["status"], PaymentTransaction.Status.PENDING)

    def test_list_only_shows_own_subscriptions_transactions(self):
        self.authenticate_as(self.user)
        self.client.post(self.url, {"amount": "5.00"})
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)

    def test_cannot_list_transactions_of_another_users_subscription(self):
        self.authenticate_as(self.user)
        others_url = reverse(
            "monetization:my-transaction-list", kwargs={"pk": self.others_sub.pk}
        )
        response = self.client.get(others_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_negative_amount_returns_400(self):
        self.authenticate_as(self.user)
        response = self.client.post(self.url, {"amount": "-5.00"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
