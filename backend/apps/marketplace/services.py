"""
Marketplace listing/image business logic.

Isolated from views/serializers, same convention as
apps.businesses.services, apps.services.services, apps.jobs.services.
Callers (views) are responsible for authorization — these functions
only enforce that the object is in a valid state for the requested
transition/operation.
"""

from django.core.exceptions import ValidationError

from .models import ListingImage, MarketplaceListing

MAX_IMAGES_PER_LISTING = 10

# ---------------------------------------------------------------------------
# Seller publish/unpublish (status)
# ---------------------------------------------------------------------------


def publish_listing(listing: MarketplaceListing) -> MarketplaceListing:
    """Seller action: make a draft/unpublished listing published (if approved)."""
    if listing.status not in (
        MarketplaceListing.Status.DRAFT,
        MarketplaceListing.Status.UNPUBLISHED,
    ):
        raise ValidationError("Only draft or unpublished listings can be published.")
    if listing.moderation_status != MarketplaceListing.ModerationStatus.APPROVED:
        raise ValidationError(
            "A listing cannot be published until it has been approved."
        )
    listing.status = MarketplaceListing.Status.PUBLISHED
    listing.save(update_fields=["status", "updated_at"])
    return listing


def unpublish_listing(listing: MarketplaceListing) -> MarketplaceListing:
    """Seller action: take a published listing down without deleting it."""
    if listing.status != MarketplaceListing.Status.PUBLISHED:
        raise ValidationError("Only published listings can be unpublished.")
    listing.status = MarketplaceListing.Status.UNPUBLISHED
    listing.save(update_fields=["status", "updated_at"])
    return listing


# ---------------------------------------------------------------------------
# Admin moderation (moderation_status) — mirrors Business verification
# ---------------------------------------------------------------------------


def approve_listing(listing: MarketplaceListing, notes: str = "") -> MarketplaceListing:
    if listing.moderation_status != MarketplaceListing.ModerationStatus.PENDING:
        raise ValidationError("Only pending listings can be approved.")
    listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
    listing.moderation_notes = notes
    listing.save(update_fields=["moderation_status", "moderation_notes", "updated_at"])
    return listing


def reject_listing(listing: MarketplaceListing, notes: str = "") -> MarketplaceListing:
    if listing.moderation_status != MarketplaceListing.ModerationStatus.PENDING:
        raise ValidationError("Only pending listings can be rejected.")
    listing.moderation_status = MarketplaceListing.ModerationStatus.REJECTED
    listing.moderation_notes = notes
    listing.save(update_fields=["moderation_status", "moderation_notes", "updated_at"])
    return listing


def request_listing_changes(
    listing: MarketplaceListing, notes: str = ""
) -> MarketplaceListing:
    if listing.moderation_status != MarketplaceListing.ModerationStatus.PENDING:
        raise ValidationError(
            "Changes can only be requested on pending listings."
        )
    listing.moderation_status = MarketplaceListing.ModerationStatus.CHANGES_REQUESTED
    listing.moderation_notes = notes
    listing.save(update_fields=["moderation_status", "moderation_notes", "updated_at"])
    return listing


def suspend_listing(listing: MarketplaceListing, notes: str = "") -> MarketplaceListing:
    if listing.moderation_status != MarketplaceListing.ModerationStatus.APPROVED:
        raise ValidationError("Only approved listings can be suspended.")
    listing.moderation_status = MarketplaceListing.ModerationStatus.SUSPENDED
    listing.moderation_notes = notes
    listing.save(update_fields=["moderation_status", "moderation_notes", "updated_at"])
    return listing


def restore_listing(listing: MarketplaceListing, notes: str = "") -> MarketplaceListing:
    if listing.moderation_status != MarketplaceListing.ModerationStatus.SUSPENDED:
        raise ValidationError("Only suspended listings can be restored.")
    listing.moderation_status = MarketplaceListing.ModerationStatus.APPROVED
    listing.moderation_notes = notes
    listing.save(update_fields=["moderation_status", "moderation_notes", "updated_at"])
    return listing


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def add_listing_image(
    listing: MarketplaceListing, image_url: str, caption: str = "", order: int = 0
) -> ListingImage:
    """
    Adds an image to a listing, enforcing the 10-image cap here (not
    at the model/DB level) so the limit is a single, testable,
    centrally-enforced business rule.
    """
    if listing.images.count() >= MAX_IMAGES_PER_LISTING:
        raise ValidationError(
            f"A listing cannot have more than {MAX_IMAGES_PER_LISTING} images."
        )
    is_primary = not listing.images.exists()  # first image is primary by default
    return ListingImage.objects.create(
        listing=listing,
        image_url=image_url,
        caption=caption,
        order=order,
        is_primary=is_primary,
    )


def set_primary_image(image: ListingImage) -> ListingImage:
    """
    Marks `image` as the listing's primary image, demoting any other
    image on the same listing that was previously primary — enforcing
    "at most one primary image per listing" centrally rather than via
    a DB constraint (which can't express "unset the others").
    """
    ListingImage.objects.filter(listing_id=image.listing_id, is_primary=True).exclude(
        pk=image.pk
    ).update(is_primary=False)
    if not image.is_primary:
        image.is_primary = True
        image.save(update_fields=["is_primary"])
    return image
