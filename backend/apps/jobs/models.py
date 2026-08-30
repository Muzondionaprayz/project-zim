from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .validators import validate_future_deadline


class JobCategory(models.Model):
    """
    A category for job postings (e.g. "Domestic Work", "IT & Tech").

    Managed via the Django admin for this phase, same as
    BusinessCategory/ServiceCategory — public read-only list, no
    public write API.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("job category")
        verbose_name_plural = _("job categories")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Job(models.Model):
    """
    A single job posting.

    "Employer" is not a separate model — ownership is always a
    direct FK to User, exactly like Business.owner. Jobs are
    deliberately decoupled from the Businesses app: posting a job
    does not require an approved (or any) business listing.

    Status transitions (draft -> open -> closed/filled) are enforced
    in services.py, not here and not in serializers — this model
    only stores the current state. Public visibility requires BOTH
    status=OPEN and a deadline that is null or still in the future
    (see is_publicly_visible / apps.jobs.views).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")
        FILLED = "filled", _("Filled")

    class JobType(models.TextChoices):
        FULL_TIME = "full_time", _("Full-time")
        PART_TIME = "part_time", _("Part-time")
        CONTRACT = "contract", _("Contract")
        GIG = "gig", _("Gig / One-off")

    class BudgetType(models.TextChoices):
        FIXED = "fixed", _("Fixed Price")
        HOURLY = "hourly", _("Hourly Rate")
        NEGOTIABLE = "negotiable", _("Negotiable")

    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    category = models.ForeignKey(
        JobCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)

    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(
        max_length=20, choices=JobType.choices, default=JobType.GIG
    )

    budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    budget_type = models.CharField(
        max_length=10, choices=BudgetType.choices, default=BudgetType.NEGOTIABLE
    )

    deadline = models.DateTimeField(
        null=True, blank=True, validators=[validate_future_deadline]
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("job")
        verbose_name_plural = _("jobs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["province"]),
            models.Index(fields=["employer"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:250] or "job"
            candidate = base_slug
            suffix = 1
            while Job.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                suffix += 1
                candidate = f"{base_slug}-{suffix}"
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.deadline is not None and self.deadline <= timezone.now()

    @property
    def is_publicly_visible(self):
        return self.status == self.Status.OPEN and not self.is_expired

    @property
    def is_accepting_applications(self):
        return self.is_publicly_visible


class JobApplication(models.Model):
    """
    An application by a User to a Job.

    `applicant` must always come from request.user, never from
    client input — the same discipline as Business.owner. A user
    may apply to a given job at most once (unique_together below is
    the hard backstop; apps.jobs.serializers also checks this ahead
    of time for a clean 400 rather than surfacing a raw IntegrityError).

    Status transitions (submitted -> reviewed -> accepted/rejected,
    or -> withdrawn) are enforced in services.py.
    """

    class Status(models.TextChoices):
        SUBMITTED = "submitted", _("Submitted")
        REVIEWED = "reviewed", _("Reviewed")
        ACCEPTED = "accepted", _("Accepted")
        REJECTED = "rejected", _("Rejected")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="applications"
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    cover_note = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.SUBMITTED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("job application")
        verbose_name_plural = _("job applications")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "applicant"], name="unique_application_per_job"
            )
        ]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.applicant} -> {self.job}"
