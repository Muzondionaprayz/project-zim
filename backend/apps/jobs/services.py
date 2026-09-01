"""
Job and JobApplication lifecycle services.

Kept isolated from views/serializers, same convention as
apps.businesses.services and apps.services.services. Callers (views)
are responsible for authorization (who may call these) — these
functions only enforce that the object is in a valid state for the
requested transition.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.messaging.models import Notification
from apps.messaging.services import notify

from .models import Job, JobApplication

# ---------------------------------------------------------------------------
# Job transitions
# ---------------------------------------------------------------------------


def publish_job(job: Job) -> Job:
    """Employer action: move a draft job to open, making it publicly visible."""
    if job.status != Job.Status.DRAFT:
        raise ValidationError("Only draft jobs can be published.")
    if job.deadline is not None and job.deadline <= timezone.now():
        raise ValidationError("Cannot publish a job whose deadline has already passed.")
    job.status = Job.Status.OPEN
    job.save(update_fields=["status", "updated_at"])
    return job


def close_job(job: Job) -> Job:
    """Employer action: stop accepting new applications on an open job."""
    if job.status != Job.Status.OPEN:
        raise ValidationError("Only open jobs can be closed.")
    job.status = Job.Status.CLOSED
    job.save(update_fields=["status", "updated_at"])
    return job


def mark_job_filled(job: Job) -> Job:
    """Employer action: mark a job as filled, from either open or closed."""
    if job.status not in (Job.Status.OPEN, Job.Status.CLOSED):
        raise ValidationError("Only open or closed jobs can be marked as filled.")
    job.status = Job.Status.FILLED
    job.save(update_fields=["status", "updated_at"])
    return job


# ---------------------------------------------------------------------------
# JobApplication transitions
# ---------------------------------------------------------------------------

_DECIDABLE_STATUSES = (JobApplication.Status.SUBMITTED, JobApplication.Status.REVIEWED)


def review_application(application: JobApplication) -> JobApplication:
    """Employer action: mark a submitted application as reviewed."""
    if application.status != JobApplication.Status.SUBMITTED:
        raise ValidationError("Only submitted applications can be marked as reviewed.")
    application.status = JobApplication.Status.REVIEWED
    application.save(update_fields=["status", "updated_at"])
    return application


def accept_application(application: JobApplication) -> JobApplication:
    """Employer action: accept an application that hasn't already been decided."""
    if application.status not in _DECIDABLE_STATUSES:
        raise ValidationError(
            "Only submitted or reviewed applications can be accepted."
        )
    application.status = JobApplication.Status.ACCEPTED
    application.save(update_fields=["status", "updated_at"])
    notify(
        recipient=application.applicant,
        notification_type=Notification.NotificationType.JOB_APPLICATION_STATUS_CHANGED,
        title="Your application was accepted",
        body=f'Your application for "{application.job.title}" was accepted.',
        related_job=application.job,
    )
    return application


def reject_application(application: JobApplication) -> JobApplication:
    """Employer action: reject an application that hasn't already been decided."""
    if application.status not in _DECIDABLE_STATUSES:
        raise ValidationError(
            "Only submitted or reviewed applications can be rejected."
        )
    application.status = JobApplication.Status.REJECTED
    application.save(update_fields=["status", "updated_at"])
    notify(
        recipient=application.applicant,
        notification_type=Notification.NotificationType.JOB_APPLICATION_STATUS_CHANGED,
        title="Your application was not successful",
        body=f'Your application for "{application.job.title}" was rejected.',
        related_job=application.job,
    )
    return application


def withdraw_application(application: JobApplication) -> JobApplication:
    """Applicant action: withdraw an application before the employer has decided."""
    if application.status not in _DECIDABLE_STATUSES:
        raise ValidationError(
            "Only submitted or reviewed applications can be withdrawn."
        )
    application.status = JobApplication.Status.WITHDRAWN
    application.save(update_fields=["status", "updated_at"])
    return application
