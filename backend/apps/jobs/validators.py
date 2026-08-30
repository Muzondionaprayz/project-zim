from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_future_deadline(value):
    """
    Rejects a deadline that is already in the past at the moment it
    is set. An absent deadline (None) means "open-ended" and is
    always valid — this validator only runs when a value is given.
    """
    if value is None:
        return
    if value <= timezone.now():
        raise ValidationError("deadline must be in the future.")
