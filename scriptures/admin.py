"""Admin configuration for the scriptures app."""

from django.contrib import admin

from scriptures.models import (
    IndexingJob,
    Scripture,
    ScriptureIndexVersion,
    Volume,
)


class VolumeInline(admin.TabularInline):
    """Inline admin for volumes within a scripture."""

    model = Volume
    extra = 0
    readonly_fields = ("file_name", "file_path", "file_size", "page_count")


@admin.register(Scripture)
class ScriptureAdmin(admin.ModelAdmin):
    """Admin for Scripture model."""

    list_display = (
        "name",
        "total_volumes",
        "total_pages",
        "is_indexed",
        "last_indexed_at",
    )
    list_filter = ("is_indexed",)
    search_fields = ("name", "description")
    inlines = [VolumeInline]
    readonly_fields = ("created_at", "last_indexed_at")


@admin.register(IndexingJob)
class IndexingJobAdmin(admin.ModelAdmin):
    list_display = ("scripture", "status", "progress", "chunks_indexed", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("scripture__name", "requested_by__email")
    readonly_fields = (
        "scripture",
        "index_version",
        "requested_by",
        "status",
        "progress",
        "celery_task_id",
        "error_message",
        "chunks_indexed",
        "volumes_processed",
        "created_at",
        "started_at",
        "finished_at",
    )


@admin.register(ScriptureIndexVersion)
class ScriptureIndexVersionAdmin(admin.ModelAdmin):
    list_display = (
        "scripture",
        "status",
        "chunk_count",
        "volume_count",
        "created_at",
        "activated_at",
    )
    list_filter = ("status", "embedding_model")
    search_fields = ("scripture__name",)
    readonly_fields = (
        "scripture",
        "status",
        "embedding_model",
        "source_manifest",
        "qualification",
        "chunk_count",
        "volume_count",
        "page_count",
        "failure_code",
        "created_at",
        "qualified_at",
        "activated_at",
    )
