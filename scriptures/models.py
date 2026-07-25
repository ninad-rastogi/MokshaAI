"""Models for the scriptures app."""

from django.conf import settings
from django.db import models


class Scripture(models.Model):
    """Represents a scripture collection (e.g., Mahabharata, Ramayana)."""

    name = models.CharField(max_length=200, unique=True)
    folder_path = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    total_volumes = models.IntegerField(default=0)
    total_pages = models.IntegerField(default=0)
    is_indexed = models.BooleanField(default=False)
    last_indexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Scripture"
        verbose_name_plural = "Scriptures"

    def __str__(self) -> str:
        return self.name


class Volume(models.Model):
    """Represents a single PDF volume within a scripture."""

    scripture = models.ForeignKey(
        Scripture, on_delete=models.CASCADE, related_name="volumes"
    )
    file_name = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000)
    file_size = models.BigIntegerField(default=0)
    page_count = models.IntegerField(default=0)
    mtime = models.FloatField(default=0.0)
    content_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["file_name"]

    def __str__(self) -> str:
        return f"{self.scripture.name} - {self.file_name}"


class IndexingJob(models.Model):
    """Durable audit record for an asynchronous scripture indexing request."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"

    scripture = models.ForeignKey(
        Scripture, on_delete=models.CASCADE, related_name="indexing_jobs"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="indexing_jobs"
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    progress = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    chunks_indexed = models.PositiveIntegerField(default=0)
    volumes_processed = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.scripture.name} ({self.status})"
