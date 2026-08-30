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


class EmployerApplicationListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other_employer = User.objects.create_user(
            email="other-employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="My Job", status=Job.Status.OPEN
        )
        self.others_job = Job.objects.create(
            employer=self.other_employer, title="Their Job", status=Job.Status.OPEN
        )
        self.application_to_own_job = JobApplication.objects.create(
            job=self.job, applicant=self.applicant
        )
        self.application_to_others_job = JobApplication.objects.create(
            job=self.others_job, applicant=self.applicant
        )

    def test_employer_can_list_applications_to_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-applications", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.application_to_own_job.id])

    def test_employer_cannot_list_applications_to_another_employers_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-applications", kwargs={"pk": self.others_job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_applicant_list_includes_contact_info_for_employer(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-applications", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        applicant_data = response.data["results"][0]["applicant"]
        self.assertEqual(applicant_data["email"], "applicant@example.com")

    def test_unauthenticated_user_cannot_list_applications(self):
        url = reverse("jobs:my-job-applications", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_applicant_cannot_list_applications_via_employer_endpoint(self):
        self.authenticate_as(self.applicant)
        url = reverse("jobs:my-job-applications", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class EmployerApplicationActionTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other_employer = User.objects.create_user(
            email="other-employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="My Job", status=Job.Status.OPEN
        )
        self.application = JobApplication.objects.create(
            job=self.job, applicant=self.applicant
        )

    def test_employer_can_review_application_to_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-review", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.REVIEWED)

    def test_other_employer_cannot_review_application_to_someone_elses_job(self):
        self.authenticate_as(self.other_employer)
        url = reverse("jobs:my-application-review", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.SUBMITTED)

    def test_applicant_cannot_review_their_own_application(self):
        self.authenticate_as(self.applicant)
        url = reverse("jobs:my-application-review", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employer_can_accept_application_to_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-accept", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.ACCEPTED)

    def test_other_employer_cannot_accept_application_to_someone_elses_job(self):
        self.authenticate_as(self.other_employer)
        url = reverse("jobs:my-application-accept", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employer_can_reject_application_to_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-reject", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, JobApplication.Status.REJECTED)

    def test_other_employer_cannot_reject_application_to_someone_elses_job(self):
        self.authenticate_as(self.other_employer)
        url = reverse("jobs:my-application-reject", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_accept(self):
        url = reverse("jobs:my-application-accept", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_transition_returns_400_not_500(self):
        """Accepting an already-rejected application is a bad request, not a server error."""
        self.application.status = JobApplication.Status.REJECTED
        self.application.save()
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-application-accept", kwargs={"pk": self.application.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
