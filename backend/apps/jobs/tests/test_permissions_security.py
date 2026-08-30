from unittest.mock import Mock

from django.test import TestCase

from apps.accounts.models import User
from apps.jobs.models import Job, JobApplication
from apps.jobs.permissions import IsApplicationOwner, IsJobOwner


class IsJobOwnerPermissionTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(employer=self.employer, title="Job")
        self.permission = IsJobOwner()

    def test_allows_employer(self):
        request = Mock(user=self.employer)
        self.assertTrue(self.permission.has_object_permission(request, None, self.job))

    def test_denies_non_employer(self):
        request = Mock(user=self.other)
        self.assertFalse(self.permission.has_object_permission(request, None, self.job))


class IsApplicationOwnerPermissionTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            email="employer@example.com", password="a-strong-passw0rd!"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com", password="a-strong-passw0rd!"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="a-strong-passw0rd!"
        )
        self.job = Job.objects.create(
            employer=self.employer, title="Job", status=Job.Status.OPEN
        )
        self.application = JobApplication.objects.create(
            job=self.job, applicant=self.applicant
        )
        self.permission = IsApplicationOwner()

    def test_allows_applicant(self):
        request = Mock(user=self.applicant)
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.application)
        )

    def test_denies_non_applicant(self):
        request = Mock(user=self.other)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.application)
        )

    def test_denies_employer_who_is_not_the_applicant(self):
        request = Mock(user=self.employer)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.application)
        )
