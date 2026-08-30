from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.businesses.models import Business


class ServiceCategory(models.Model):
    """
    A category for services offered on the platform (e.g. "Haircuts",
    "Home Repairs"). Deliberately separate from BusinessCategory —
    a business's category describes the business itself, while a
    service's category describes one specific offering it provides.

    Managed via the Django admin for this phase, same as
    BusinessCategory — public read-only list, no public write API.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("service category")
        verbose_name_plural = _("service categories")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Service(models.Model):
    """
    A single service offered by a Business.

    There is no independent "service owner" — ownership is always
    derived transitively through `business.owner`. The view layer
    must always scope/validate against request.user's own
    businesses; a client must never be able to set `business` to a
    business it doesn't own (see apps.services.serializers).

    Public visibility requires BOTH:
      - this Service having is_active=True, AND
      - its parent Business having status=APPROVED

    Unlike Business, Service has no independent verification
    workflow this phase — it inherits its parent business's
    verification status rather than needing its own admin approval.
    A dedicated Service moderation workflow (if ever needed) belongs
    to a later phase, built the same way Business's was: as an
    isolated services.py, not bolted onto this model or its
    serializers.
    """

    class PriceType(models.TextChoices):
        FIXED = "fixed", _("Fixed Price")
        HOURLY = "hourly", _("Hourly Rate")
        QUOTE = "quote", _("Quote on Request")

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="services"
    )
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    price_type = models.CharField(
        max_length=10, choices=PriceType.choices, default=PriceType.QUOTE
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    is_active = models.BooleanField(
        default=True,
        help_text=_(
            "Owner-controlled publish toggle. A service is only "
            "publicly visible when this is True AND the parent "
            "business is approved."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("service")
        verbose_name_plural = _("services")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:250] or "service"
            candidate = base_slug
            suffix = 1
            while (
                Service.objects.filter(slug=candidate)
                .exclude(pk=self.pk)
                .exists()
            ):
                suffix += 1
                candidate = f"{base_slug}-{suffix}"
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_publicly_visible(self):
        return self.is_active and self.business.is_publicly_visible
