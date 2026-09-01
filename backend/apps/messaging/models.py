from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
    """
    A two-user conversation thread. Users relate to it only through
    ConversationParticipant (never a direct M2M) so there is a place
    to hang each participant's own read cursor.

    Optionally linked to the Job or Marketplace listing it started
    from (e.g. "inquire about this job/listing") — both nullable and
    SET_NULL so deleting the Job/Listing never deletes conversation
    history. Business/Service intentionally have no equivalent link:
    "message the business owner" is already just a plain two-user
    conversation with no extra state to attach.

    `is_active` is a simple open/closed flag — there is no richer
    status lifecycle needed for a two-user thread in this phase.
    """

    related_job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    related_listing = models.ForeignKey(
        "marketplace.MarketplaceListing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("conversation")
        verbose_name_plural = _("conversations")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation<{self.pk}>"


class ConversationParticipant(models.Model):
    """
    Links a User to a Conversation. This is the only way a user is
    "in" a conversation — there is no direct User<->Conversation M2M.

    `last_read_at` is the entire read-state mechanism: a message is
    considered read by this participant if its created_at is <= this
    timestamp. No per-message read record exists (see
    apps.messaging.services for the documented tradeoff) — a single
    cursor is sufficient for a two-participant thread and avoids an
    O(messages x participants) table.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participations",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("conversation participant")
        verbose_name_plural = _("conversation participants")
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="unique_participant_per_conversation"
            )
        ]

    def __str__(self):
        return f"{self.user} in Conversation<{self.conversation_id}>"


class Message(models.Model):
    """
    A single message in a Conversation. Immutable once sent — there
    is no edit/delete endpoint in this phase (see the Phase 8 plan),
    so this model deliberately has no `updated_at`.

    `sender` must always come from request.user in the view layer —
    never from client input, same discipline as Business.owner/
    Job.employer/MarketplaceListing.seller.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"Message<{self.pk}> in Conversation<{self.conversation_id}>"


class Notification(models.Model):
    """
    A generic in-app notification for one recipient. `recipient` must
    always come from server-side logic — never client input.

    Uses explicit nullable FKs for context (rather than a generic
    (type, id) pointer) to stay consistent with how the rest of the
    project links records — e.g. Business.category — plain FKs, no
    contenttypes/generic relations.
    """

    class NotificationType(models.TextChoices):
        NEW_MESSAGE = "new_message", _("New Message")
        JOB_APPLICATION_RECEIVED = (
            "job_application_received",
            _("Job Application Received"),
        )
        JOB_APPLICATION_STATUS_CHANGED = (
            "job_application_status_changed",
            _("Job Application Status Changed"),
        )
        LISTING_MODERATION_RESULT = (
            "listing_moderation_result",
            _("Listing Moderation Result"),
        )
        BUSINESS_VERIFICATION_RESULT = (
            "business_verification_result",
            _("Business Verification Result"),
        )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=40, choices=NotificationType.choices
    )
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=500, blank=True)

    related_conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True
    )
    related_listing = models.ForeignKey(
        "marketplace.MarketplaceListing", on_delete=models.SET_NULL, null=True, blank=True
    )
    related_business = models.ForeignKey(
        "businesses.Business", on_delete=models.SET_NULL, null=True, blank=True
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self):
        return f"Notification<{self.pk}> to {self.recipient}"
