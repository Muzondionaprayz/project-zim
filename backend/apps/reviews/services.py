"""
Review creation and moderation business logic.

Isolated from views/serializers, same convention as
apps.businesses.services / apps.services.services / apps.jobs.services
/ apps.marketplace.services / apps.messaging.services. Unlike those
apps, review *creation* validation (not just post-creation state
transitions) also lives here — self-review, target-eligibility, and
duplicate checks are all business rules about what makes a review
valid, not input-shape validation, so they belong in services.py per
the Phase 9 requirement to centralize business logic there.
"""

from django.core.exceptions import ValidationError

from apps.adminpanel.services import log_action

from .models import Review


def _target_and_owner_id(business, service, marketplace_listing):
    """
    Returns (target, owner_id) for whichever of the three optional
    targets was supplied. Raises ValidationError if zero or more
    than one was given — a review must target exactly one entity.
    """
    targets = [t for t in (business, service, marketplace_listing) if t is not None]
    if len(targets) != 1:
        raise ValidationError(
            "A review must target exactly one of business, service, or marketplace listing."
        )
    target = targets[0]

    if business is not None:
        owner_id = business.owner_id
    elif service is not None:
        owner_id = service.business.owner_id
    else:
        owner_id = marketplace_listing.seller_id

    return target, owner_id


def create_review(
    reviewer, *, business=None, service=None, marketplace_listing=None, rating, body=""
) -> Review:
    """
    Creates a Review after enforcing:
      - exactly one target was supplied
      - the target is currently publicly visible (you can't review a
        draft/unapproved listing nobody else can even see)
      - the reviewer does not own the target (no self-reviews)
      - the reviewer hasn't already reviewed this exact target
        (the DB's partial unique constraints are the hard backstop;
        this check exists to surface a clean validation error instead
        of a raw IntegrityError)
    """
    target, owner_id = _target_and_owner_id(business, service, marketplace_listing)

    if not target.is_publicly_visible:
        raise ValidationError("You can only review publicly visible listings.")

    if owner_id == reviewer.id:
        raise ValidationError("You cannot review your own listing.")

    duplicate_exists = Review.objects.filter(
        reviewer=reviewer, business=business, service=service, marketplace_listing=marketplace_listing
    ).exists()
    if duplicate_exists:
        raise ValidationError("You have already reviewed this listing.")

    return Review.objects.create(
        reviewer=reviewer,
        business=business,
        service=service,
        marketplace_listing=marketplace_listing,
        rating=rating,
        body=body,
    )


def hide_review(review: Review, notes: str = "", actor=None) -> Review:
    """Admin action: hide a published review from public view."""
    if review.status != Review.Status.PUBLISHED:
        raise ValidationError("Only published reviews can be hidden.")
    review.status = Review.Status.HIDDEN
    review.moderation_notes = notes
    review.save(update_fields=["status", "moderation_notes", "updated_at"])
    if actor is not None:
        log_action(
            actor=actor,
            action="review.hidden",
            target_type="review",
            target_id=review.id,
            details=notes,
        )
    return review


def restore_review(review: Review, notes: str = "", actor=None) -> Review:
    """Admin action: restore a hidden review back to published."""
    if review.status != Review.Status.HIDDEN:
        raise ValidationError("Only hidden reviews can be restored.")
    review.status = Review.Status.PUBLISHED
    review.moderation_notes = notes
    review.save(update_fields=["status", "moderation_notes", "updated_at"])
    if actor is not None:
        log_action(
            actor=actor,
            action="review.restored",
            target_type="review",
            target_id=review.id,
            details=notes,
        )
    return review
