"""Serializers for the scriptures app."""

from rest_framework import serializers

from scriptures.models import IndexingJob, Scripture, Volume


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


class ScriptureSerializer(serializers.ModelSerializer):
    """Serializer for Scripture model with nested volumes."""

    volumes = VolumeSerializer(many=True, read_only=True)

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
            "created_at",
            "volumes",
        )


class IndexingJobSerializer(serializers.ModelSerializer):
    """Expose job progress without leaking unrelated user information."""

    scripture_name = serializers.CharField(source="scripture.name", read_only=True)

    class Meta:
        model = IndexingJob
        fields = (
            "id",
            "scripture",
            "scripture_name",
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
