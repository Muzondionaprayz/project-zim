from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class MarketplaceCategory(models.Model):
    """Mirrors BusinessCategory/ServiceCategory/JobCategory."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("marketplace category")
        verbose_name_plural = _("marketplace categories")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class MarketplaceListing(models.Model):
    """
    A single marketplace listing (classifieds-style item for sale).

    "Seller" is not a separate model — ownership is always a direct
    FK to User, same pattern as Business.owner/Job.employer. Never
    trust a client-supplied seller; it is set only from request.user
    in the view layer (see apps.marketplace.views).

    Two independent state fields, both enforced only via services.py:
      - `status` (draft/published/unpublished) — the seller's own
        publish/unpublish control.
      - `moderation_status` (pending/approved/rejected/
        changes_requested/suspended) — the admin verification
        pipeline, mirroring Business's verification_status pattern.

    Public visibility requires BOTH status=PUBLISHED AND
    moderation_status=APPROVED (see is_publicly_visible).
    """

    class Condition(models.TextChoices):
        NEW = "new", _("New")
        USED_LIKE_NEW = "used_like_new", _("Used - Like New")
        USED_GOOD = "used_good", _("Used - Good")
        USED_FAIR = "used_fair", _("Used - Fair")

    class PriceType(models.TextChoices):
        FIXED = "fixed", _("Fixed Price")
        NEGOTIABLE = "negotiable", _("Negotiable")
        SWAP = "swap", _("Swap / Trade")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        UNPUBLISHED = "unpublished", _("Unpublished")

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", _("Pending Review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        CHANGES_REQUESTED = "changes_requested", _("Changes Requested")
        SUSPENDED = "suspended", _("Suspended")

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marketplace_listings"
    )
    category = models.ForeignKey(
        MarketplaceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listings",
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
        max_length=12, choices=PriceType.choices, default=PriceType.FIXED
    )
    condition = models.CharField(
        max_length=15, choices=Condition.choices, default=Condition.USED_GOOD
    )

    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT
    )
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    moderation_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("marketplace listing")
        verbose_name_plural = _("marketplace listings")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["moderation_status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["province"]),
            models.Index(fields=["seller"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:250] or "listing"
            candidate = base_slug
            suffix = 1
            while (
                MarketplaceListing.objects.filter(slug=candidate)
                .exclude(pk=self.pk)
                .exists()
            ):
                suffix += 1
                candidate = f"{base_slug}-{suffix}"
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_publicly_visible(self):
        return (
            self.status == self.Status.PUBLISHED
            and self.moderation_status == self.ModerationStatus.APPROVED
        )


class ListingImage(models.Model):
    """
    A single image attached to a MarketplaceListing.

    At most 10 images per listing and at most 1 primary image per
    listing are enforced in services.py, not here — keeping this
    model a plain record and the invariants centrally testable/
    enforced in one place, same convention as status transitions
    elsewhere in the project.
    """

    listing = models.ForeignKey(
        MarketplaceListing, on_delete=models.CASCADE, related_name="images"
    )
    image_url = models.URLField()
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("listing image")
        verbose_name_plural = _("listing images")
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"Image<{self.listing_id}:{self.order}>"
