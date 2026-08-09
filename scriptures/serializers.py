"""Serializers for the scriptures app."""

from rest_framework import serializers

from scriptures.models import (
    IndexingJob,
    Scripture,
    ScriptureIndexVersion,
    Volume,
)


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

    class Meta:
        model = IndexingJob
        fields = (
            "status",
            "progress",
            "chunks_indexed",
            "volumes_processed",
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

    class Meta:
        model = IndexingJob
        fields = (
            "id",
            "scripture",
            "scripture_name",
            "index_version",
            "status",
            "progress",
            "error_message",
            "chunks_indexed",
            "volumes_processed",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields
