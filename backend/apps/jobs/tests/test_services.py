from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.jobs import services
from apps.jobs.models import Job, JobApplication


class PublishJobServiceTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )

    def test_publish_draft_job_succeeds(self):
        job = Job.objects.create(employer=self.employer, title="Job")
        services.publish_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.OPEN)

    def test_publish_non_draft_job_is_rejected(self):
        job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        with self.assertRaises(ValidationError):
            services.publish_job(job)

    def test_publish_job_with_past_deadline_is_rejected(self):
        job = Job.objects.create(employer=self.employer, title="Job")
        Job.objects.filter(pk=job.pk).update(deadline=timezone.now() - timedelta(days=1))
        job.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.publish_job(job)


class CloseJobServiceTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )

    def test_close_open_job_succeeds(self):
        job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        services.close_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.CLOSED)

    def test_close_draft_job_is_rejected(self):
        job = Job.objects.create(employer=self.employer, title="Job")
        with self.assertRaises(ValidationError):
            services.close_job(job)


class MarkJobFilledServiceTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )

    def test_mark_open_job_filled_succeeds(self):
        job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        services.mark_job_filled(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.FILLED)

    def test_mark_closed_job_filled_succeeds(self):
        job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.CLOSED
        )
        services.mark_job_filled(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.FILLED)

    def test_mark_draft_job_filled_is_rejected(self):
        job = Job.objects.create(employer=self.employer, title="Job")
        with self.assertRaises(ValidationError):
            services.mark_job_filled(job)


class ApplicationTransitionServiceTests(TestCase):
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

    def _submitted_application(self):
        return JobApplication.objects.create(job=self.job, applicant=self.applicant)

    def test_review_submitted_application_succeeds(self):
        application = self._submitted_application()
        services.review_application(application)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.REVIEWED)

    def test_review_non_submitted_application_is_rejected(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.ACCEPTED
        application.save()
        with self.assertRaises(ValidationError):
            services.review_application(application)

    def test_accept_submitted_application_succeeds(self):
        application = self._submitted_application()
        services.accept_application(application)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.ACCEPTED)

    def test_accept_reviewed_application_succeeds(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.REVIEWED
        application.save()
        services.accept_application(application)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.ACCEPTED)

    def test_accept_already_rejected_application_is_rejected(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.REJECTED
        application.save()
        with self.assertRaises(ValidationError):
            services.accept_application(application)

    def test_reject_submitted_application_succeeds(self):
        application = self._submitted_application()
        services.reject_application(application)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.REJECTED)

    def test_reject_already_accepted_application_is_rejected(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.ACCEPTED
        application.save()
        with self.assertRaises(ValidationError):
            services.reject_application(application)

    def test_withdraw_submitted_application_succeeds(self):
        application = self._submitted_application()
        services.withdraw_application(application)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.WITHDRAWN)

    def test_withdraw_reviewed_application_succeeds(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.REVIEWED
        application.save()
        services.withdraw_application(application)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.WITHDRAWN)

    def test_withdraw_accepted_application_is_rejected(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.ACCEPTED
        application.save()
        with self.assertRaises(ValidationError):
            services.withdraw_application(application)

    def test_withdraw_rejected_application_is_rejected(self):
        application = self._submitted_application()
        application.status = JobApplication.Status.REJECTED
        application.save()
        with self.assertRaises(ValidationError):
            services.withdraw_application(application)
