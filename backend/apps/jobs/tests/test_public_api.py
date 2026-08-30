from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.jobs.models import Job, JobCategory


class PublicJobListTests(APITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.category = JobCategory.objects.create(name="Domestic Work")

        self.open_job = Job.objects.create(
            employer=self.employer,
            title="Open Job",
            status=Job.Status.OPEN,
            city="Harare",
            province="Harare",
            category=self.category,
        )
        self.draft_job = Job.objects.create(
            employer=self.employer, title="Draft Job", status=Job.Status.DRAFT
        )
        self.closed_job = Job.objects.create(
            employer=self.employer, title="Closed Job", status=Job.Status.CLOSED
        )
        self.filled_job = Job.objects.create(
            employer=self.employer, title="Filled Job", status=Job.Status.FILLED
        )
        # Expired: OPEN but deadline already passed (set directly to bypass validator).
        self.expired_job = Job.objects.create(
            employer=self.employer, title="Expired Job", status=Job.Status.OPEN
        )
        Job.objects.filter(pk=self.expired_job.pk).update(
            deadline=timezone.now() - timedelta(days=1)
        )

        self.url = reverse("jobs:public-list")

    def test_list_is_accessible_without_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_contains_open_non_expired_jobs(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Open Job"])

    def test_list_excludes_draft_closed_filled_expired(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        for hidden in ["Draft Job", "Closed Job", "Filled Job", "Expired Job"]:
            self.assertNotIn(hidden, titles)

    def test_list_response_excludes_employer_field(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertNotIn("employer", item)

    def test_filter_by_category(self):
        Job.objects.create(
            employer=self.employer, title="Uncategorized Open Job", status=Job.Status.OPEN
        )
        response = self.client.get(self.url, {"category": self.category.slug})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Open Job"])

    def test_filter_by_city(self):
        Job.objects.create(
            employer=self.employer,
            title="Bulawayo Job",
            status=Job.Status.OPEN,
            city="Bulawayo",
        )
        response = self.client.get(self.url, {"city": "Harare"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Open Job"])

    def test_search_by_title(self):
        response = self.client.get(self.url, {"search": "Open Job"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Open Job"])

    def test_open_job_with_future_deadline_is_listed(self):
        future_job = Job.objects.create(
            employer=self.employer,
            title="Future Deadline Job",
            status=Job.Status.OPEN,
            deadline=timezone.now() + timedelta(days=10),
        )
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertIn("Future Deadline Job", titles)


class PublicJobDetailTests(APITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.open_job = Job.objects.create(
            employer=self.employer, title="Open Job", status=Job.Status.OPEN
        )
        self.draft_job = Job.objects.create(
            employer=self.employer, title="Draft Job", status=Job.Status.DRAFT
        )

    def test_detail_accessible_without_authentication(self):
        url = reverse("jobs:public-detail", kwargs={"pk": self.open_job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detail_excludes_employer_field(self):
        url = reverse("jobs:public-detail", kwargs={"pk": self.open_job.pk})
        response = self.client.get(url)
        self.assertNotIn("employer", response.data)

    def test_draft_job_detail_returns_404(self):
        url = reverse("jobs:public-detail", kwargs={"pk": self.draft_job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_job_returns_404(self):
        url = reverse("jobs:public-detail", kwargs={"pk": 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class JobCategoryListTests(APITestCase):
    def test_category_list_is_public(self):
        JobCategory.objects.create(name="Domestic Work")
        url = reverse("jobs:category-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_inactive_categories_are_excluded(self):
        JobCategory.objects.create(name="Active Cat", is_active=True)
        JobCategory.objects.create(name="Inactive Cat", is_active=False)
        url = reverse("jobs:category-list")
        response = self.client.get(url)
        names = [item["name"] for item in response.data]
        self.assertEqual(names, ["Active Cat"])
