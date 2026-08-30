from django.core.exceptions import ValidationError

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def validate_opening_hours(value):
    """
    Validates the shape of Business.opening_hours.

    Expected shape (all keys optional):
        {"monday": {"open": "08:00", "close": "17:00"}, "sunday": None, ...}

    Keeps validation structural only — it does not parse or compare
    times, which is intentionally out of scope for this phase.
    """
    if not value:
        return

    if not isinstance(value, dict):
        raise ValidationError("opening_hours must be an object keyed by day of week.")

    for day, hours in value.items():
        if day not in WEEKDAYS:
            raise ValidationError(
                f"'{day}' is not a valid day of the week. Expected one of: "
                f"{', '.join(WEEKDAYS)}."
            )

        if hours is None:
            continue

        if not isinstance(hours, dict):
            raise ValidationError(
                f"Hours for '{day}' must be an object with 'open' and 'close', or null."
            )

        unexpected_keys = set(hours.keys()) - {"open", "close"}
        if unexpected_keys:
            raise ValidationError(
                f"Unexpected key(s) for '{day}': {', '.join(sorted(unexpected_keys))}."
            )

        for key in ("open", "close"):
            if key in hours and not isinstance(hours[key], str):
                raise ValidationError(
                    f"'{key}' for '{day}' must be a time string (e.g. '09:00')."
                )
