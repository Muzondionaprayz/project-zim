from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.jobs.models import Job


class AuthenticatedAPITestCase(APITestCase):
    def authenticate_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class MyJobCreateTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.url = reverse("jobs:my-job-list")
        self.payload = {"title": "New Job", "city": "Harare", "province": "Harare"}

    def test_unauthenticated_user_cannot_create_job(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Job.objects.filter(title="New Job").exists())

    def test_authenticated_user_can_create_job(self):
        self.authenticate_as(self.employer)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Job.objects.filter(title="New Job").exists())

    def test_created_job_employer_is_request_user(self):
        self.authenticate_as(self.employer)
        response = self.client.post(self.url, self.payload)
        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.employer, self.employer)

    def test_client_cannot_spoof_employer_via_field(self):
        """
        Submitting another user's ID as "employer" must be silently
        ignored — the created job must still belong to request.user.
        """
        self.authenticate_as(self.employer)
        payload = {**self.payload, "employer": self.other_user.id}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.employer, self.employer)
        self.assertNotEqual(job.employer, self.other_user)

    def test_created_job_defaults_to_draft(self):
        self.authenticate_as(self.employer)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.data["status"], Job.Status.DRAFT)

    def test_client_cannot_set_status_at_creation(self):
        self.authenticate_as(self.employer)
        payload = {**self.payload, "status": "open"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.data["status"], Job.Status.DRAFT)

    def test_response_never_contains_employer_field(self):
        self.authenticate_as(self.employer)
        response = self.client.post(self.url, self.payload)
        self.assertNotIn("employer", response.data)


class MyJobListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.own_job = Job.objects.create(employer=self.employer, title="My Job")
        self.others_job = Job.objects.create(employer=self.other_user, title="Their Job")
        self.url = reverse("jobs:my-job-list")

    def test_list_only_returns_own_jobs(self):
        self.authenticate_as(self.employer)
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["My Job"])

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyJobDetailTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(employer=self.employer, title="My Job")
        self.others_job = Job.objects.create(employer=self.other_user, title="Their Job")

    def test_owner_can_view_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.job.pk})
        response = self.client.patch(url, {"description": "Updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.description, "Updated")

    def test_user_cannot_view_another_users_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.others_job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_modify_another_users_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.others_job.pk})
        response = self.client.patch(url, {"description": "Hacked!"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_job.refresh_from_db()
        self.assertNotEqual(self.others_job.description, "Hacked!")

    def test_user_cannot_delete_another_users_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.others_job.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Job.objects.filter(pk=self.others_job.pk).exists())

    def test_owner_can_delete_own_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.job.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Job.objects.filter(pk=self.job.pk).exists())

    def test_owner_cannot_change_status_via_update(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.job.pk})
        response = self.client.patch(url, {"status": "open"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.DRAFT)

    def test_owner_cannot_change_employer_via_update(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.job.pk})
        response = self.client.patch(url, {"employer": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.employer, self.employer)

    def test_unauthenticated_user_cannot_view_job_detail(self):
        url = reverse("jobs:my-job-detail", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class JobLifecycleActionAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(employer=self.employer, title="My Job")

    def test_owner_can_publish_own_draft_job(self):
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-publish", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.OPEN)

    def test_user_cannot_publish_another_users_job(self):
        self.authenticate_as(self.other_user)
        url = reverse("jobs:my-job-publish", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.DRAFT)

    def test_publishing_already_open_job_is_rejected(self):
        self.job.status = Job.Status.OPEN
        self.job.save()
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-publish", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_close_own_open_job(self):
        self.job.status = Job.Status.OPEN
        self.job.save()
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-close", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.CLOSED)

    def test_user_cannot_close_another_users_job(self):
        self.job.status = Job.Status.OPEN
        self.job.save()
        self.authenticate_as(self.other_user)
        url = reverse("jobs:my-job-close", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_mark_own_job_filled(self):
        self.job.status = Job.Status.OPEN
        self.job.save()
        self.authenticate_as(self.employer)
        url = reverse("jobs:my-job-mark-filled", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.FILLED)

    def test_user_cannot_mark_another_users_job_filled(self):
        self.job.status = Job.Status.OPEN
        self.job.save()
        self.authenticate_as(self.other_user)
        url = reverse("jobs:my-job-mark-filled", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_publish(self):
        url = reverse("jobs:my-job-publish", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
