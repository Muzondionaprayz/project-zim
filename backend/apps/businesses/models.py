from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .validators import validate_opening_hours


class BusinessCategory(models.Model):
    """
    A directory category (e.g. "Plumbing", "Salon & Beauty").

    Managed by staff via the Django admin for this phase — there is
    no public write API for categories yet, only a public read list
    so clients can populate filters/dropdowns.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("business category")
        verbose_name_plural = _("business categories")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Business(models.Model):
    """
    A single business directory listing.

    Ownership (`owner`) must always be set from `request.user` in the
    view layer — never from client-supplied input. Visibility to the
    public is governed entirely by `status`; only APPROVED businesses
    are ever returned by public endpoints (see apps.businesses.views).

    Status transitions (draft -> pending -> approved/rejected/...)
    are enforced in services.py, not here and not in serializers —
    this model only stores the current state.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PENDING = "pending", _("Pending Verification")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        CHANGES_REQUESTED = "changes_requested", _("Changes Requested")
        SUSPENDED = "suspended", _("Suspended")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="businesses",
    )
    category = models.ForeignKey(
        BusinessCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="businesses",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)

    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    logo_url = models.URLField(blank=True)
    cover_image_url = models.URLField(blank=True)
    opening_hours = models.JSONField(
        default=dict, blank=True, validators=[validate_opening_hours]
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    # Staff-facing feedback for the current/last verification decision
    # (rejection reason, requested changes, suspension reason, etc.).
    # Never exposed on public endpoints.
    verification_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("business")
        verbose_name_plural = _("businesses")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["province"]),
            models.Index(fields=["owner"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:250] or "business"
            candidate = base_slug
            suffix = 1
            while (
                Business.objects.filter(slug=candidate)
                .exclude(pk=self.pk)
                .exists()
            ):
                suffix += 1
                candidate = f"{base_slug}-{suffix}"
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_publicly_visible(self):
        return self.status == self.Status.APPROVED
