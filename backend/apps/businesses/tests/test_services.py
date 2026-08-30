from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.businesses import services
from apps.businesses.models import Business


class SubmitForVerificationServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )

    def test_submit_from_draft_moves_to_pending(self):
        business = Business.objects.create(owner=self.owner, name="Draft Biz")
        services.submit_for_verification(business)
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.PENDING)
        self.assertIsNotNone(business.submitted_at)

    def test_submit_from_changes_requested_moves_to_pending(self):
        business = Business.objects.create(
            owner=self.owner, name="Changes Biz", status=Business.Status.CHANGES_REQUESTED
        )
        services.submit_for_verification(business)
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.PENDING)

    def test_submit_from_approved_is_rejected(self):
        business = Business.objects.create(
            owner=self.owner, name="Approved Biz", status=Business.Status.APPROVED
        )
        with self.assertRaises(ValidationError):
            services.submit_for_verification(business)

    def test_submit_from_pending_is_rejected(self):
        business = Business.objects.create(
            owner=self.owner, name="Pending Biz", status=Business.Status.PENDING
        )
        with self.assertRaises(ValidationError):
            services.submit_for_verification(business)


class AdminVerificationServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="a-strong-passw0rd!"
        )

    def _pending_business(self, **kwargs):
        return Business.objects.create(
            owner=self.owner, name="Pending Biz", status=Business.Status.PENDING, **kwargs
        )

    def test_approve_pending_business(self):
        business = self._pending_business()
        services.approve_business(business, notes="Looks good")
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.APPROVED)
        self.assertEqual(business.verification_notes, "Looks good")
        self.assertIsNotNone(business.verified_at)

    def test_approve_non_pending_business_is_rejected(self):
        business = Business.objects.create(owner=self.owner, name="Draft Biz")
        with self.assertRaises(ValidationError):
            services.approve_business(business)

    def test_reject_pending_business(self):
        business = self._pending_business()
        services.reject_business(business, notes="Incomplete info")
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.REJECTED)
        self.assertEqual(business.verification_notes, "Incomplete info")

    def test_reject_non_pending_business_is_rejected(self):
        business = Business.objects.create(owner=self.owner, name="Draft Biz")
        with self.assertRaises(ValidationError):
            services.reject_business(business)

    def test_request_changes_on_pending_business(self):
        business = self._pending_business()
        services.request_changes(business, notes="Add a phone number")
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.CHANGES_REQUESTED)
        self.assertEqual(business.verification_notes, "Add a phone number")

    def test_request_changes_on_non_pending_business_is_rejected(self):
        business = Business.objects.create(owner=self.owner, name="Draft Biz")
        with self.assertRaises(ValidationError):
            services.request_changes(business)

    def test_suspend_approved_business(self):
        business = Business.objects.create(
            owner=self.owner, name="Live Biz", status=Business.Status.APPROVED
        )
        services.suspend_business(business, notes="Complaint received")
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.SUSPENDED)

    def test_suspend_non_approved_business_is_rejected(self):
        business = self._pending_business()
        with self.assertRaises(ValidationError):
            services.suspend_business(business)

    def test_restore_suspended_business(self):
        business = Business.objects.create(
            owner=self.owner, name="Suspended Biz", status=Business.Status.SUSPENDED
        )
        services.restore_business(business)
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.APPROVED)

    def test_restore_non_suspended_business_is_rejected(self):
        business = self._pending_business()
        with self.assertRaises(ValidationError):
            services.restore_business(business)
