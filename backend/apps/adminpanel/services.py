"""
Admin business logic: audit logging and user administration.

`log_action` is the single entry point other apps' services.py files
call (additively — see apps.businesses.services, apps.marketplace.services,
apps.reviews.services) to record an admin action, mirroring how
apps.messaging.services.notify() became the single entry point for
notifications in Phase 8. It has no knowledge of *why* it's being
called; each domain decides when to call it.
"""

from django.core.exceptions import ValidationError

from .models import AuditLog


def log_action(actor, action: str, target_type: str = "", target_id=None, details: str = "") -> AuditLog:
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


def change_user_role(admin_user, target_user, role: str) -> "User":  # noqa: F821
    """
    Admin action: change another user's role.

    Refuses to let an admin change their own role — this is the
    self-demotion/lockout guard, not a restriction on promoting other
    users (granting the admin role to someone else is a normal,
    intended admin capability).
    """
    if target_user.id == admin_user.id:
        raise ValidationError("You cannot change your own role.")

    target_user.role = role
    target_user.save(update_fields=["role"])
    log_action(
        actor=admin_user,
        action="user.role_changed",
        target_type="user",
        target_id=target_user.id,
        details=f"role set to {role}",
    )
    return target_user


def activate_user(admin_user, target_user) -> "User":  # noqa: F821
    """Admin action: reactivate a deactivated account."""
    if target_user.is_active:
        raise ValidationError("This account is already active.")
    target_user.is_active = True
    target_user.save(update_fields=["is_active"])
    log_action(
        actor=admin_user,
        action="user.activated",
        target_type="user",
        target_id=target_user.id,
    )
    return target_user


def deactivate_user(admin_user, target_user) -> "User":  # noqa: F821
    """
    Admin action: deactivate an account.

    Refuses to let an admin deactivate themselves — the self-lockout
    guard mirroring change_user_role's own-role protection.
    """
    if target_user.id == admin_user.id:
        raise ValidationError("You cannot deactivate your own account.")
    if not target_user.is_active:
        raise ValidationError("This account is already inactive.")

    target_user.is_active = False
    target_user.save(update_fields=["is_active"])
    log_action(
        actor=admin_user,
        action="user.deactivated",
        target_type="user",
        target_id=target_user.id,
    )
    return target_user
