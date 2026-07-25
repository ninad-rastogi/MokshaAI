"""Models for the chat app."""

import uuid

from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class DocumentChunk(models.Model):
    """A scripture fragment and its native pgvector embedding."""

    scripture = models.CharField(max_length=200, db_index=True)
    file_name = models.CharField(max_length=500)
    page = models.IntegerField()
    chunk_text = models.TextField()
    chunk_type = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=10, blank=True)
    index_version = models.UUIDField(null=True, db_index=True)
    # Nullable only to permit an upgrade of pre-pgvector rows; indexing replaces them.
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_chunks"
        indexes = [
            models.Index(fields=["scripture"]),
        ]

    def __str__(self) -> str:
        return f"{self.scripture} - {self.file_name} p{self.page}"


class Chat(models.Model):
    """Represents a chat session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chats",
    )
    name = models.CharField(max_length=50, default="New Spiritual Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.name}"


class Message(models.Model):
    """Represents a single message within a chat session."""

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20)  # "user" or "assistant"
    content = models.TextField()
    mode = models.CharField(max_length=20, blank=True)  # "RAG", "GENERAL", "ERROR"
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.chat.name} - {self.role}"


class GenerationRun(models.Model):
    """Durable lifecycle record for one assistant generation."""

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="runs")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generation_runs",
    )
    idempotency_key = models.CharField(max_length=255)
    prompt = models.TextField()
    model_profile = models.CharField(max_length=120, blank=True)
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.QUEUED,
        db_index=True,
    )
    user_message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generation_user_runs",
    )
    assistant_message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generation_assistant_runs",
    )
    stream_key = models.CharField(max_length=255, unique=True)
    last_event_id = models.CharField(max_length=64, blank=True)
    final_text = models.TextField(blank=True)
    final_sources = models.JSONField(default=list, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-queued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["chat", "idempotency_key"],
                name="uniq_generation_run_chat_idempotency",
            )
        ]

    def __str__(self) -> str:
        return f"{self.chat_id} - {self.state}"


class GenerationAttempt(models.Model):
    """Immutable-ish provider attempt snapshot for a run."""

    class Outcome(models.TextChoices):
        STARTED = "started", "Started"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    run = models.ForeignKey(
        GenerationRun,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveSmallIntegerField()
    provider = models.CharField(max_length=80)
    model = models.CharField(max_length=160)
    model_snapshot = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.STARTED,
    )
    error_code = models.CharField(max_length=80, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    cost = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "attempt_number"],
                name="uniq_generation_attempt_number",
            )
        ]
