from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.jobs.models import Job, JobApplication


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class ApplyToJobTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.open_job = Job.objects.create(
            employer=self.employer, title="Open Job", status=Job.Status.OPEN
        )
        self.closed_job = Job.objects.create(
            employer=self.employer, title="Closed Job", status=Job.Status.CLOSED
        )
        self.filled_job = Job.objects.create(
            employer=self.employer, title="Filled Job", status=Job.Status.FILLED
        )
        self.url = reverse("jobs:my-applications-list")

    def test_unauthenticated_user_cannot_apply(self):
        response = self.client.post(self.url, {"job": self.open_job.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_apply_to_open_job(self):
        self.authenticate_as(self.applicant)
        response = self.client.post(
            self.url, {"job": self.open_job.id, "cover_note": "I would love this job"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            JobApplication.objects.filter(job=self.open_job, applicant=self.applicant).exists()
        )

    def test_applicant_is_derived_from_request_user(self):
        self.authenticate_as(self.applicant)
        response = self.client.post(self.url, {"job": self.open_job.id})
        application = JobApplication.objects.get(id=response.data["id"])
        self.assertEqual(application.applicant, self.applicant)

    def test_client_cannot_spoof_applicant_field(self):
        """
        There is no writable "applicant" field at all — even if a
        client includes one, the application still belongs to
        request.user, never to the supplied ID.
        """
        other_user = User.objects.create_user(
            email="innocent@example.com", password="a-strong-passw0rd!"
        )
        self.authenticate_as(self.applicant)
        response = self.client.post(
            self.url, {"job": self.open_job.id, "applicant": other_user.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = JobApplication.objects.get(id=response.data["id"])
        self.assertEqual(application.applicant, self.applicant)
        self.assertNotEqual(application.applicant, other_user)

    def test_cannot_apply_to_own_job(self):
        self.authenticate_as(self.employer)
        response = self.client.post(self.url, {"job": self.open_job.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job", response.data)
        self.assertFalse(
            JobApplication.objects.filter(job=self.open_job, applicant=self.employer).exists()
        )

    def test_cannot_apply_twice_to_the_same_job(self):
        self.authenticate_as(self.applicant)
        first = self.client.post(self.url, {"job": self.open_job.id})
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(self.url, {"job": self.open_job.id})
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job", second.data)
        self.assertEqual(
            JobApplication.objects.filter(job=self.open_job, applicant=self.applicant).count(),
            1,
        )

    def test_cannot_apply_to_closed_job(self):
        self.authenticate_as(self.applicant)
        response = self.client.post(self.url, {"job": self.closed_job.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_apply_to_filled_job(self):
        self.authenticate_as(self.applicant)
        response = self.client.post(self.url, {"job": self.filled_job.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_apply_to_draft_job(self):
        draft_job = Job.objects.create(employer=self.employer, title="Draft Job")
        self.authenticate_as(self.applicant)
        response = self.client.post(self.url, {"job": draft_job.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_apply_to_expired_job(self):
        from datetime import timedelta

        from django.utils import timezone

        expired_job = Job.objects.create(
            employer=self.employer, title="Expired Job", status=Job.Status.OPEN
        )
        Job.objects.filter(pk=expired_job.pk).update(
            deadline=timezone.now() - timedelta(days=1)
        )
        self.authenticate_as(self.applicant)
        response = self.client.post(self.url, {"job": expired_job.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job", response.data)

    def test_created_application_defaults_to_submitted(self):
        self.authenticate_as(self.applicant)
        response = self.client.post(self.url, {"job": self.open_job.id})
        self.assertEqual(response.data["status"], JobApplication.Status.SUBMITTED)

    def test_client_cannot_set_status_at_creation(self):
        self.authenticate_as(self.applicant)
        response = self.client.post(
            self.url, {"job": self.open_job.id, "status": "accepted"}
        )
        self.assertEqual(response.data["status"], JobApplication.Status.SUBMITTED)


class MyApplicationListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.other_applicant = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        self.own_application = JobApplication.objects.create(
            job=self.job, applicant=self.applicant
        )
        self.others_application = JobApplication.objects.create(
            job=self.job, applicant=self.other_applicant
        )
        self.url = reverse("jobs:my-applications-list")

    def test_list_only_returns_own_applications(self):
        self.authenticate_as(self.applicant)
        response = self.client.get(self.url)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.own_application.id])

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyApplicationDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.other_applicant = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        self.own_application = JobApplication.objects.create(
            job=self.job, applicant=self.applicant
        )
        self.others_application = JobApplication.objects.create(
            job=self.job, applicant=self.other_applicant
        )

    def test_applicant_can_view_own_application(self):
        self.authenticate_as(self.applicant)
        url = reverse("jobs:my-application-detail", kwargs={"pk": self.own_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_applicant_cannot_view_another_applicants_application(self):
        self.authenticate_as(self.applicant)
        url = reverse(
            "jobs:my-application-detail", kwargs={"pk": self.others_application.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employer_cannot_view_application_via_applicant_endpoint(self):
        """The applicant-facing detail endpoint is scoped to applicant, not employer."""
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-detail", kwargs={"pk": self.own_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_view_application(self):
        url = reverse("jobs:my-application-detail", kwargs={"pk": self.own_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class WithdrawApplicationTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.other_applicant = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        self.application = JobApplication.objects.create(
            job=self.job, applicant=self.applicant
        )

    def test_applicant_can_withdraw_own_application(self):
        self.authenticate_as(self.applicant)
        url = reverse("jobs:my-application-withdraw", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.WITHDRAWN)

    def test_other_user_cannot_withdraw_someone_elses_application(self):
        self.authenticate_as(self.other_applicant)
        url = reverse("jobs:my-application-withdraw", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.SUBMITTED)

    def test_employer_cannot_withdraw_application_via_applicant_endpoint(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-withdraw", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_withdraw_already_accepted_application(self):
        self.application.status = JobApplication.Status.ACCEPTED
        self.application.save()
        self.authenticate_as(self.applicant)
        url = reverse("jobs:my-application-withdraw", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_user_cannot_withdraw(self):
        url = reverse("jobs:my-application-withdraw", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
