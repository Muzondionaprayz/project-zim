from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message, Notification


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    readonly_fields = ["joined_at"]


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "body", "created_at"]
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "related_job", "related_listing", "is_active", "created_at"]
    list_filter = ["is_active"]
    inlines = [ConversationParticipantInline, MessageInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "recipient", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["recipient__email", "title"]
    readonly_fields = ["created_at", "read_at"]
