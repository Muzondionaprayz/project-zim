from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.adminpanel.models import AuditLog
from apps.businesses.models import Business
from apps.marketplace.models import MarketplaceListing
from apps.reviews.models import Review


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class AdminBusinessListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.approved = Business.objects.create(
            owner=self.owner, name="Approved Biz", status=Business.Status.APPROVED
        )
        self.draft = Business.objects.create(owner=self.owner, name="Draft Biz")
        self.url = reverse("adminpanel:business-list")

    def test_admin_sees_all_businesses_regardless_of_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Approved Biz", "Draft Biz"})

    def test_ordinary_user_cannot_access_admin_business_list(self):
        self.authenticate_as(self.ordinary_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"status": "draft"})
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Draft Biz"])

    def test_admin_list_includes_owner_email(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        item = next(i for i in response.data["results"] if i["name"] == "Approved Biz")
        self.assertEqual(item["owner_email"], "owner@example.com")

    def test_admin_list_includes_verification_notes(self):
        self.draft.verification_notes = "needs more info"
        self.draft.save()
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"status": "draft"})
        self.assertEqual(response.data["results"][0]["verification_notes"], "needs more info")


class AdminMarketplaceListingListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.seller = User.objects.create_user(
            email="seller@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.pending = MarketplaceListing.objects.create(seller=self.seller, title="Pending Item")
        self.approved = MarketplaceListing.objects.create(
            seller=self.seller,
            title="Approved Item",
            status=MarketplaceListing.Status.PUBLISHED,
            moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
        )
        self.url = reverse("adminpanel:marketplace-listing-list")

    def test_admin_sees_all_listings_regardless_of_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(titles, {"Pending Item", "Approved Item"})

    def test_ordinary_user_cannot_access(self):
        self.authenticate_as(self.ordinary_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_moderation_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"moderation_status": "pending"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Pending Item"])

    def test_admin_list_includes_seller_email(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        item = next(i for i in response.data["results"] if i["title"] == "Pending Item")
        self.assertEqual(item["seller_email"], "seller@example.com")


class AdminReviewListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com", password="a-strong-passw0rd!"
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.APPROVED
        )
        self.other_business = Business.objects.create(
            owner=self.owner, name="Other Biz", status=Business.Status.APPROVED
        )
        self.published = Review.objects.create(
            reviewer=self.reviewer, business=self.business, rating=5
        )
        self.hidden = Review.objects.create(
            reviewer=self.reviewer,
            business=self.other_business,
            rating=1,
            status=Review.Status.HIDDEN,
        )
        self.url = reverse("adminpanel:review-list")

    def test_admin_sees_all_reviews_regardless_of_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {self.published.id, self.hidden.id})

    def test_ordinary_user_cannot_access(self):
        self.authenticate_as(self.ordinary_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_status(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"status": "hidden"})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.hidden.id])

    def test_admin_list_includes_reviewer_email(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        item = next(i for i in response.data["results"] if i["id"] == self.published.id)
        self.assertEqual(item["reviewer_email"], "reviewer@example.com")


class AdminAuditLogListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.ordinary_user = User.objects.create_user(
            email="ordinary@example.com", password="a-strong-passw0rd!"
        )
        AuditLog.objects.create(
            actor=self.admin, action="business.approved", target_type="business", target_id=1
        )
        AuditLog.objects.create(
            actor=self.admin, action="review.hidden", target_type="review", target_id=2
        )
        self.url = reverse("adminpanel:audit-log-list")

    def test_admin_can_view_audit_log(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_ordinary_user_cannot_view_audit_log(self):
        self.authenticate_as(self.ordinary_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_view_audit_log(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_action(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"action": "review.hidden"})
        actions = [item["action"] for item in response.data["results"]]
        self.assertEqual(actions, ["review.hidden"])

    def test_filter_by_target_type(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.url, {"target_type": "business"})
        target_types = [item["target_type"] for item in response.data["results"]]
        self.assertEqual(target_types, ["business"])

    def test_no_write_endpoint_exists_for_audit_log(self):
        self.authenticate_as(self.admin)
        response = self.client.post(self.url, {"action": "fake.action"})
        self.assertIn(
            response.status_code,
            (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN),
        )


class DomainActionsCreateAuditLogEntriesTests(AuthenticatedAPITestCase):
    """
    End-to-end confirmation that the existing (Phase 3/6/9) moderation
    endpoints — unchanged in shape — now additionally produce a
    visible audit trail through the new admin endpoint.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="a-strong-passw0rd!", role=User.Role.ADMIN
        )
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Biz", status=Business.Status.PENDING
        )

    def test_approving_a_business_via_existing_endpoint_creates_audit_entry(self):
        self.authenticate_as(self.admin)
        url = reverse("businesses:admin-approve", kwargs={"pk": self.business.pk})
        self.client.post(url, {"notes": "looks good"})

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin, action="business.approved", target_id=self.business.id
            ).exists()
        )

    def test_audit_entry_visible_via_admin_audit_log_endpoint(self):
        self.authenticate_as(self.admin)
        approve_url = reverse("businesses:admin-approve", kwargs={"pk": self.business.pk})
        self.client.post(approve_url)

        audit_url = reverse("adminpanel:audit-log-list")
        response = self.client.get(audit_url)
        actions = [item["action"] for item in response.data["results"]]
        self.assertIn("business.approved", actions)
