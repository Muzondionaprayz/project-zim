from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    """
    A rating/review left by a User against a Business, Service, or
    MarketplaceListing. Exactly one of `business`/`service`/
    `marketplace_listing` must be set — enforced in
    apps.reviews.services.create_review, not here (a structural
    "exactly one of N nullable FKs" invariant doesn't map cleanly
    onto a Django CheckConstraint the way the project's other
    DB-backed invariants do).

    `reviewer` must always come from request.user — never trusted
    from client input, same discipline as Business.owner/
    Job.employer/MarketplaceListing.seller/Message.sender.

    Jobs are deliberately not reviewable in this phase — see the
    Phase 9 plan for the reasoning (no established "completed job"
    two-sided review relationship exists yet).

    Moderation is a simple two-state flip (published/hidden), not a
    submission-for-approval pipeline like Business/MarketplaceListing
    — reviews are visible immediately and only removed reactively.
    """

    class Status(models.TextChoices):
        PUBLISHED = "published", _("Published")
        HIDDEN = "hidden", _("Hidden")

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written"
    )
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, null=True, blank=True, related_name="reviews"
    )
    service = models.ForeignKey(
        "services.Service", on_delete=models.CASCADE, null=True, blank=True, related_name="reviews"
    )
    marketplace_listing = models.ForeignKey(
        "marketplace.MarketplaceListing",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reviews",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField(blank=True, max_length=2000, validators=[MaxLengthValidator(2000)])

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PUBLISHED)
    # Admin-only context for why a review was hidden/restored. Never
    # exposed on any public endpoint (see serializers.py).
    moderation_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        ordering = ["-created_at"]
        constraints = [
            # Three partial unique indexes, not one combined constraint
            # across all three nullable FKs: a plain multi-column
            # UNIQUE constraint would never flag two rows as
            # duplicates when the differentiating columns are both
            # NULL (SQL's NULL != NULL), so a reviewer could otherwise
            # leave unlimited duplicate reviews on the same service.
            # Each partial index only covers rows where that specific
            # target column is set, avoiding the NULL-comparison gap.
            models.UniqueConstraint(
                fields=["reviewer", "business"],
                condition=Q(business__isnull=False),
                name="unique_review_per_reviewer_business",
            ),
            models.UniqueConstraint(
                fields=["reviewer", "service"],
                condition=Q(service__isnull=False),
                name="unique_review_per_reviewer_service",
            ),
            models.UniqueConstraint(
                fields=["reviewer", "marketplace_listing"],
                condition=Q(marketplace_listing__isnull=False),
                name="unique_review_per_reviewer_listing",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Review<{self.pk}> by {self.reviewer}"

    @property
    def is_publicly_visible(self):
        return self.status == self.Status.PUBLISHED

    @property
    def target(self):
        return self.business or self.service or self.marketplace_listing
