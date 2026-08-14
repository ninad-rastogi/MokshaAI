"""Models for the scriptures app."""

import uuid

from django.conf import settings
from django.db import models


class Scripture(models.Model):
    """Represents one auto-discovered spiritual text collection."""

    name = models.CharField(max_length=200, unique=True)
    folder_path = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    total_volumes = models.IntegerField(default=0)
    total_pages = models.IntegerField(default=0)
    is_indexed = models.BooleanField(default=False)
    last_indexed_at = models.DateTimeField(null=True, blank=True)
    active_index_version = models.ForeignKey(
        "ScriptureIndexVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_for_scriptures",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Scripture"
        verbose_name_plural = "Scriptures"

    def __str__(self) -> str:
        return self.name

    @property
    def current_indexing_job(self):
        jobs = getattr(self, "active_indexing_jobs", None)
        if jobs is not None:
            return jobs[0] if jobs else None
        return self.indexing_jobs.filter(
            status__in=[IndexingJob.Status.PENDING, IndexingJob.Status.RUNNING]
        ).first()

    @property
    def latest_indexing_failure(self):
        jobs = getattr(self, "failed_indexing_jobs", None)
        if jobs is not None:
            return jobs[0] if jobs else None
        return self.indexing_jobs.filter(status=IndexingJob.Status.FAILED).first()


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


class ScriptureIndexVersion(models.Model):
    """Immutable candidate or completed index build for one collection."""

    class Status(models.TextChoices):
        BUILDING = "building", "Building"
        QUALIFIED = "qualified", "Qualified"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scripture = models.ForeignKey(
        Scripture,
        on_delete=models.CASCADE,
        related_name="index_versions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BUILDING,
        db_index=True,
    )
    embedding_model = models.CharField(max_length=200)
    source_manifest = models.JSONField(default=list)
    qualification = models.JSONField(default=dict, blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    volume_count = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    failure_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qualified_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["scripture", "status"])]

    def __str__(self) -> str:
        return f"{self.scripture.name} {self.id} ({self.status})"


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
    index_version = models.ForeignKey(
        ScriptureIndexVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
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
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["scripture"],
                condition=models.Q(status__in=["PENDING", "RUNNING"]),
                name="uniq_active_scripture_indexing_job",
            )
        ]

    def __str__(self) -> str:
        return f"{self.scripture.name} ({self.status})"

    @property
    def source_volumes(self) -> int:
        index_version = self.index_version
        if index_version is not None and index_version.volume_count:
            return index_version.volume_count
        return self.scripture.total_volumes

    @property
    def source_pages(self) -> int:
        index_version = self.index_version
        if index_version is not None and index_version.page_count:
            return index_version.page_count
        return self.scripture.total_pages
