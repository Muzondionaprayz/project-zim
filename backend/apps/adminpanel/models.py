from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """
    A record of an administrative action taken on the platform.

    `target_type`/`target_id` are plain fields, not a Django
    GenericForeignKey — consistent with how Notification (Phase 8)
    and Review (Phase 9) both chose explicit fields over a generic
    relation. A GenericForeignKey would also force every new
    domain to be pre-registered via ContentType; plain fields let an
    audit entry reference any target (including ones from domains
    that don't otherwise need a relation back to admin) without any
    schema coupling.

    `actor` is SET_NULL rather than CASCADE — deleting an admin
    account should never delete the historical record of what they
    did.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("audit log entry")
        verbose_name_plural = _("audit log entries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.created_at}"
