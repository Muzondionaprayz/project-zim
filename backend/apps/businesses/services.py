"""
Business lifecycle / verification services.

This is the intentionally small integration point for verification.
It enforces valid status transitions and timestamps them; it does
NOT implement a moderation queue, notifications, audit trail, or
admin dashboard — those belong to a later, dedicated Admin phase and
should be built around these functions rather than duplicating their
transition logic elsewhere.

Callers (views) are responsible for authorization (who may call
these) — these functions only enforce that the *business* is in a
valid state for the requested transition.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Business

_SUBMITTABLE_STATUSES = (Business.Status.DRAFT, Business.Status.CHANGES_REQUESTED)


def submit_for_verification(business: Business) -> Business:
    """Owner action: move a draft (or changes-requested) business into the review queue."""
    if business.status not in _SUBMITTABLE_STATUSES:
        raise ValidationError(
            "Only draft or changes-requested businesses can be submitted for verification."
        )
    business.status = Business.Status.PENDING
    business.submitted_at = timezone.now()
    business.save(update_fields=["status", "submitted_at", "updated_at"])
    return business


def approve_business(business: Business, notes: str = "") -> Business:
    """Admin action: approve a pending business, making it publicly visible."""
    if business.status != Business.Status.PENDING:
        raise ValidationError("Only pending businesses can be approved.")
    business.status = Business.Status.APPROVED
    business.verification_notes = notes
    business.verified_at = timezone.now()
    business.save(
        update_fields=["status", "verification_notes", "verified_at", "updated_at"]
    )
    return business


def reject_business(business: Business, notes: str = "") -> Business:
    """Admin action: reject a pending business."""
    if business.status != Business.Status.PENDING:
        raise ValidationError("Only pending businesses can be rejected.")
    business.status = Business.Status.REJECTED
    business.verification_notes = notes
    business.save(update_fields=["status", "verification_notes", "updated_at"])
    return business


def request_changes(business: Business, notes: str = "") -> Business:
    """Admin action: send a pending business back to the owner with requested changes."""
    if business.status != Business.Status.PENDING:
        raise ValidationError(
            "Changes can only be requested on pending businesses."
        )
    business.status = Business.Status.CHANGES_REQUESTED
    business.verification_notes = notes
    business.save(update_fields=["status", "verification_notes", "updated_at"])
    return business


def suspend_business(business: Business, notes: str = "") -> Business:
    """Admin action: suspend a currently-approved business, hiding it from the public."""
    if business.status != Business.Status.APPROVED:
        raise ValidationError("Only approved businesses can be suspended.")
    business.status = Business.Status.SUSPENDED
    business.verification_notes = notes
    business.save(update_fields=["status", "verification_notes", "updated_at"])
    return business


def restore_business(business: Business, notes: str = "") -> Business:
    """Admin action: restore a suspended business back to approved/public."""
    if business.status != Business.Status.SUSPENDED:
        raise ValidationError("Only suspended businesses can be restored.")
    business.status = Business.Status.APPROVED
    business.verification_notes = notes
    business.save(update_fields=["status", "verification_notes", "updated_at"])
    return business
