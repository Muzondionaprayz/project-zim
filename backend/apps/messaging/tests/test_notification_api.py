from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.messaging import services
from apps.messaging.models import Notification


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class NotificationListAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.own_notification = services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Mine",
        )
        self.others_notification = services.notify(
            recipient=self.other_user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Theirs",
        )
        self.url = reverse("notifications:list")

    def test_list_only_returns_own_notifications(self):
        self.authenticate_as(self.user)
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.own_notification.id])

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MarkNotificationReadAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.own_notification = services.notify(
            recipient=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Mine",
        )
        self.others_notification = services.notify(
            recipient=self.other_user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Theirs",
        )

    def test_owner_can_mark_own_notification_read(self):
        self.authenticate_as(self.user)
        url = reverse("notifications:mark-read", kwargs={"pk": self.own_notification.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_notification.refresh_from_db()
        self.assertTrue(self.own_notification.is_read)

    def test_cannot_mark_another_users_notification_read(self):
        self.authenticate_as(self.user)
        url = reverse(
            "notifications:mark-read", kwargs={"pk": self.others_notification.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_notification.refresh_from_db()
        self.assertFalse(self.others_notification.is_read)

    def test_unauthenticated_cannot_mark_read(self):
        url = reverse("notifications:mark-read", kwargs={"pk": self.own_notification.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_notification_returns_404(self):
        self.authenticate_as(self.user)
        url = reverse("notifications:mark-read", kwargs={"pk": 999999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MarkAllNotificationsReadAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        for i in range(3):
            services.notify(
                recipient=self.user,
                notification_type=Notification.NotificationType.NEW_MESSAGE,
                title=f"Mine {i}",
            )
        self.others_notification = services.notify(
            recipient=self.other_user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="Theirs",
        )
        self.url = reverse("notifications:mark-all-read")

    def test_marks_all_own_notifications_read(self):
        self.authenticate_as(self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["marked_read"], 3)
        self.assertEqual(
            Notification.objects.filter(recipient=self.user, is_read=False).count(), 0
        )

    def test_does_not_affect_other_users_notifications(self):
        self.authenticate_as(self.user)
        self.client.post(self.url)
        self.others_notification.refresh_from_db()
        self.assertFalse(self.others_notification.is_read)

    def test_unauthenticated_cannot_mark_all_read(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DomainTriggeredNotificationAPITests(AuthenticatedAPITestCase):
    """Confirms notifications actually fire from the existing domain flows via the API."""

    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )

    def test_job_application_notifies_employer(self):
        from apps.jobs.models import Job

        job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        self.authenticate_as(self.applicant)
        url = reverse("jobs:my-applications-list")
        self.client.post(url, {"job": job.id})

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.employer,
                notification_type=Notification.NotificationType.JOB_APPLICATION_RECEIVED,
            ).exists()
        )

    def test_job_application_accept_notifies_applicant(self):
        from apps.jobs.models import Job, JobApplication

        job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        application = JobApplication.objects.create(job=job, applicant=self.applicant)
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-accept", kwargs={"pk": application.pk})
        self.client.post(url)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.applicant,
                notification_type=Notification.NotificationType.JOB_APPLICATION_STATUS_CHANGED,
            ).exists()
        )

    def test_business_approval_notifies_owner(self):
        from apps.accounts.models import User as AccountUser
        from apps.businesses.models import Business

        admin = AccountUser.objects.create_user(
            email="admin@example.com",
            password="a-strong-passw0rd!",
            role=AccountUser.Role.ADMIN,
        )
        business = Business.objects.create(
            owner=self.employer, name="Biz", status=Business.Status.PENDING
        )
        self.authenticate_as(admin)
        url = reverse("businesses:admin-approve", kwargs={"pk": business.pk})
        self.client.post(url)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.employer,
                notification_type=Notification.NotificationType.BUSINESS_VERIFICATION_RESULT,
            ).exists()
        )

    def test_listing_approval_notifies_seller(self):
        from apps.accounts.models import User as AccountUser
        from apps.marketplace.models import MarketplaceListing

        admin = AccountUser.objects.create_user(
            email="admin2@example.com",
            password="a-strong-passw0rd!",
            role=AccountUser.Role.ADMIN,
        )
        listing = MarketplaceListing.objects.create(
            seller=self.applicant, title="Item"
        )
        self.authenticate_as(admin)
        url = reverse("marketplace:admin-approve", kwargs={"pk": listing.pk})
        self.client.post(url)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.applicant,
                notification_type=Notification.NotificationType.LISTING_MODERATION_RESULT,
            ).exists()
        )
