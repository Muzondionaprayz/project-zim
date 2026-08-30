"""
Service business logic.

Deliberately small: Service has no multi-state verification workflow
this phase (see models.Service docstring) — it only has an
owner-controlled publish toggle. These functions exist anyway, in
their own module, so that toggle logic doesn't end up duplicated or
inlined into views/serializers, and so a future richer workflow (if
ever needed) has an obvious place to grow into rather than requiring
a refactor out of the view layer.
"""

from django.core.exceptions import ValidationError

from .models import Service


def activate_service(service: Service) -> Service:
    """Publish a service. Requires the parent business to be approved."""
    if not service.business.is_publicly_visible:
        raise ValidationError(
            "A service cannot be activated while its business is not approved."
        )
    service.is_active = True
    service.save(update_fields=["is_active", "updated_at"])
    return service


def deactivate_service(service: Service) -> Service:
    """Unpublish a service without deleting it."""
    service.is_active = False
    service.save(update_fields=["is_active", "updated_at"])
    return service
