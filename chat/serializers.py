"""Serializers for the chat app."""

from rest_framework import serializers

from chat.models import Chat, GenerationAttempt, GenerationRun, Message


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""

    class Meta:
        model = Message
        fields = ("id", "role", "content", "mode", "sources", "created_at")
        read_only_fields = ("id", "created_at")


class ChatSerializer(serializers.ModelSerializer):
    """Serializer for Chat model with message count."""

    message_count = serializers.IntegerField(source="messages.count", read_only=True)

    class Meta:
        model = Chat
        fields = (
            "id",
            "name",
            "created_at",
            "updated_at",
            "message_count",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ChatDetailSerializer(serializers.ModelSerializer):
    """Serializer for Chat model with full message history."""

    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Chat
        fields = ("id", "name", "created_at", "updated_at", "messages")
        read_only_fields = ("id", "created_at", "updated_at")


class QuerySerializer(serializers.Serializer):
    """Serializer for chat query requests."""

    message = serializers.CharField(max_length=5000)


class QueryResponseSerializer(serializers.Serializer):
    """Serializer for chat query responses."""

    response = serializers.CharField()
    sources = serializers.ListField(child=serializers.DictField(), required=False)
    mode = serializers.CharField()


class RunCreateSerializer(serializers.Serializer):
    """Create a durable generation run."""

    message = serializers.CharField(max_length=5000)
    model_profile = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )


class GenerationAttemptSerializer(serializers.ModelSerializer):
    """Read-only serializer for a generation attempt."""

    class Meta:
        model = GenerationAttempt
        fields = (
            "attempt_number",
            "provider",
            "model",
            "model_snapshot",
            "outcome",
            "error_code",
            "usage",
            "cost",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class GenerationRunSerializer(serializers.ModelSerializer):
    """Read-only serializer for a durable generation run."""

    attempts = GenerationAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = GenerationRun
        fields = (
            "id",
            "chat",
            "state",
            "model_profile",
            "last_event_id",
            "final_text",
            "final_sources",
            "error_code",
            "queued_at",
            "started_at",
            "finished_at",
            "updated_at",
            "attempts",
        )
        read_only_fields = fields
