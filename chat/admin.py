"""Admin configuration for the chat app."""

from django.contrib import admin

from chat.models import Chat, GenerationAttempt, GenerationRun, Message


class MessageInline(admin.TabularInline):
    """Inline admin for messages within a chat."""

    model = Message
    extra = 0
    readonly_fields = ("role", "content", "mode", "sources", "created_at")
    can_delete = False


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    """Admin for Chat model."""

    list_display = ("name", "user", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("name", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin for Message model."""

    list_display = ("chat", "role", "mode", "created_at")
    list_filter = ("role", "mode", "created_at")
    search_fields = ("content", "chat__name")
    readonly_fields = ("sources", "created_at")


class GenerationAttemptInline(admin.TabularInline):
    """Inline admin for generation attempts."""

    model = GenerationAttempt
    extra = 0
    readonly_fields = (
        "attempt_number",
        "provider",
        "model",
        "outcome",
        "error_code",
        "started_at",
        "finished_at",
    )
    can_delete = False


@admin.register(GenerationRun)
class GenerationRunAdmin(admin.ModelAdmin):
    """Admin for durable generation runs."""

    list_display = ("id", "chat", "user", "state", "model_profile", "queued_at")
    list_filter = ("state", "model_profile", "queued_at")
    search_fields = ("id", "chat__name", "user__email", "idempotency_key")
    readonly_fields = (
        "id",
        "stream_key",
        "last_event_id",
        "queued_at",
        "updated_at",
    )
    inlines = [GenerationAttemptInline]
