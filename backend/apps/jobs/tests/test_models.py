from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.jobs.models import Job, JobApplication, JobCategory


class JobCategoryModelTests(TestCase):
    def test_slug_is_auto_generated_from_name(self):
        category = JobCategory.objects.create(name="Domestic Work & Care")
        self.assertEqual(category.slug, "domestic-work-care")

    def test_str_returns_name(self):
        category = JobCategory.objects.create(name="IT & Tech")
        self.assertEqual(str(category), "IT & Tech")


class JobModelTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )

    def test_job_defaults_to_draft_status(self):
        job = Job.objects.create(employer=self.employer, title="Gardener Needed")
        self.assertEqual(job.status, Job.Status.DRAFT)

    def test_slug_is_auto_generated_from_title(self):
        job = Job.objects.create(employer=self.employer, title="Gardener Needed")
        self.assertTrue(job.slug.startswith("gardener-needed"))

    def test_duplicate_titles_get_unique_slugs(self):
        first = Job.objects.create(employer=self.employer, title="Cleaner")
        second = Job.objects.create(employer=self.employer, title="Cleaner")
        self.assertNotEqual(first.slug, second.slug)

    def test_deleting_employer_deletes_job(self):
        job = Job.objects.create(employer=self.employer, title="Doomed Job")
        job_id = job.id
        self.employer.delete()
        self.assertFalse(Job.objects.filter(id=job_id).exists())

    def test_deleting_category_sets_null_not_cascade(self):
        category = JobCategory.objects.create(name="Cat")
        job = Job.objects.create(
            employer=self.employer, title="Cat Job", category=category
        )
        category.delete()
        job.refresh_from_db()
        self.assertIsNone(job.category)

    def test_negative_budget_fails_validation(self):
        job = Job(employer=self.employer, title="Bad Budget", budget=Decimal("-10"))
        with self.assertRaises(ValidationError):
            job.full_clean()

    def test_past_deadline_fails_validation(self):
        job = Job(
            employer=self.employer,
            title="Past Deadline",
            deadline=timezone.now() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            job.full_clean()

    def test_future_deadline_passes_validation(self):
        job = Job(
            employer=self.employer,
            title="Future Deadline",
            deadline=timezone.now() + timedelta(days=7),
        )
        job.full_clean()  # should not raise

    def test_null_deadline_passes_validation(self):
        job = Job(employer=self.employer, title="No Deadline")
        job.full_clean()  # should not raise

    def test_is_expired_true_when_deadline_passed(self):
        job = Job.objects.create(
            employer=self.employer,
            title="Expired Job",
            status=Job.Status.OPEN,
        )
        # Bypass validator by updating directly, simulating time passing.
        Job.objects.filter(pk=job.pk).update(deadline=timezone.now() - timedelta(days=1))
        job.refresh_from_db()
        self.assertTrue(job.is_expired)

    def test_is_expired_false_when_no_deadline(self):
        job = Job.objects.create(employer=self.employer, title="Open Ended Job")
        self.assertFalse(job.is_expired)

    def test_is_publicly_visible_requires_open_and_not_expired(self):
        job = Job.objects.create(employer=self.employer, title="Draft Job")
        self.assertFalse(job.is_publicly_visible)

        job.status = Job.Status.OPEN
        job.save()
        self.assertTrue(job.is_publicly_visible)

        Job.objects.filter(pk=job.pk).update(deadline=timezone.now() - timedelta(days=1))
        job.refresh_from_db()
        self.assertFalse(job.is_publicly_visible)

    def test_str_returns_title(self):
        job = Job.objects.create(employer=self.employer, title="String Job")
        self.assertEqual(str(job), "String Job")


class JobApplicationModelTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )

    def test_application_defaults_to_submitted_status(self):
        application = JobApplication.objects.create(job=self.job, applicant=self.applicant)
        self.assertEqual(application.status, JobApplication.Status.SUBMITTED)

    def test_duplicate_application_is_rejected_at_db_level(self):
        JobApplication.objects.create(job=self.job, applicant=self.applicant)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JobApplication.objects.create(job=self.job, applicant=self.applicant)

    def test_same_applicant_can_apply_to_different_jobs(self):
        other_job = Job.objects.create(
            employer=self.employer, title="Other Job", status=Job.Status.OPEN
        )
        JobApplication.objects.create(job=self.job, applicant=self.applicant)
        JobApplication.objects.create(job=other_job, applicant=self.applicant)
        self.assertEqual(
            JobApplication.objects.filter(applicant=self.applicant).count(), 2
        )

    def test_deleting_job_deletes_applications(self):
        application = JobApplication.objects.create(job=self.job, applicant=self.applicant)
        application_id = application.id
        self.job.delete()
        self.assertFalse(JobApplication.objects.filter(id=application_id).exists())

    def test_deleting_applicant_deletes_applications(self):
        application = JobApplication.objects.create(job=self.job, applicant=self.applicant)
        application_id = application.id
        self.applicant.delete()
        self.assertFalse(JobApplication.objects.filter(id=application_id).exists())

    def test_str_representation(self):
        application = JobApplication.objects.create(job=self.job, applicant=self.applicant)
        self.assertIn(str(self.applicant), str(application))
