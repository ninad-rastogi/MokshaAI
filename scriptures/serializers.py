"""Serializers for the scriptures app."""

from rest_framework import serializers

from scriptures.models import (
    IndexingJob,
    Scripture,
    ScriptureIndexVersion,
    Volume,
)


def indexing_display_progress(job: IndexingJob) -> int:
    source_pages = job.source_pages
    if (
        job.status == IndexingJob.Status.RUNNING
        and indexing_phase(job) == "ocr"
        and job.chunks_indexed > 0
        and source_pages > 0
        and job.chunks_indexed < source_pages
    ):
        percentage = round(job.chunks_indexed / source_pages * 100)
        return max(1, min(69, percentage))
    return job.progress


def indexing_phase(job: IndexingJob) -> str:
    """Expose a bounded indexing phase without leaking internal failure details."""
    if job.status == IndexingJob.Status.PENDING:
        return "queued"
    if job.error_message == "ocr_fallback_running":
        return "ocr"
    if job.progress < 70:
        return "reading_source"
    if job.progress < 85:
        return "embedding"
    if job.progress < 100:
        return "qualifying"
    return "activating"


class VolumeSerializer(serializers.ModelSerializer):
    """Serializer for Volume model."""

    class Meta:
        model = Volume
        fields = (
            "id",
            "file_name",
            "file_path",
            "file_size",
            "page_count",
            "mtime",
        )


class IndexingProgressSerializer(serializers.ModelSerializer):
    """Bounded active indexing progress safe for authenticated users."""

    source_volumes = serializers.IntegerField(read_only=True)
    source_pages = serializers.IntegerField(read_only=True)
    progress = serializers.SerializerMethodField()
    phase = serializers.SerializerMethodField()

    def get_progress(self, job: IndexingJob) -> int:
        return indexing_display_progress(job)

    def get_phase(self, job: IndexingJob) -> str:
        return indexing_phase(job)

    class Meta:
        model = IndexingJob
        fields = (
            "status",
            "phase",
            "progress",
            "chunks_indexed",
            "volumes_processed",
            "source_volumes",
            "source_pages",
        )
        read_only_fields = fields


class IndexingFailureSerializer(serializers.ModelSerializer):
    """Bounded failure state without internal exception details."""

    failure_code = serializers.CharField(source="error_message", read_only=True)

    class Meta:
        model = IndexingJob
        fields = ("failure_code", "finished_at")
        read_only_fields = fields


class ScriptureSerializer(serializers.ModelSerializer):
    """Serializer for Scripture model with nested volumes."""

    volumes = VolumeSerializer(many=True, read_only=True)
    active_index_version: serializers.PrimaryKeyRelatedField = (
        serializers.PrimaryKeyRelatedField(read_only=True)
    )
    current_indexing_job = IndexingProgressSerializer(read_only=True)
    latest_indexing_failure = IndexingFailureSerializer(read_only=True)

    class Meta:
        model = Scripture
        fields = (
            "id",
            "name",
            "folder_path",
            "description",
            "total_volumes",
            "total_pages",
            "is_indexed",
            "last_indexed_at",
            "active_index_version",
            "current_indexing_job",
            "latest_indexing_failure",
            "created_at",
            "volumes",
        )


class ScriptureIndexVersionSerializer(serializers.ModelSerializer):
    """Bounded immutable index-version status."""

    class Meta:
        model = ScriptureIndexVersion
        fields = (
            "id",
            "status",
            "embedding_model",
            "qualification",
            "chunk_count",
            "volume_count",
            "page_count",
            "failure_code",
            "created_at",
            "qualified_at",
            "activated_at",
        )
        read_only_fields = fields


class IndexingJobSerializer(serializers.ModelSerializer):
    """Expose job progress without leaking unrelated user information."""

    scripture_name = serializers.CharField(source="scripture.name", read_only=True)
    progress = serializers.SerializerMethodField()
    phase = serializers.SerializerMethodField()

    def get_progress(self, job: IndexingJob) -> int:
        return indexing_display_progress(job)

    def get_phase(self, job: IndexingJob) -> str:
        return indexing_phase(job)

    class Meta:
        model = IndexingJob
        fields = (
            "id",
            "scripture",
            "scripture_name",
            "index_version",
            "status",
            "phase",
            "progress",
            "error_message",
            "chunks_indexed",
            "volumes_processed",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields
