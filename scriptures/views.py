"""Views for the scriptures app."""

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from chat.models import DocumentChunk
from scriptures.models import IndexingJob, Scripture, ScriptureIndexVersion
from scriptures.serializers import (
    IndexingJobSerializer,
    ScriptureIndexVersionSerializer,
    ScriptureSerializer,
)
from scriptures.tasks import index_scripture


class ScriptureViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving scriptures."""

    queryset = Scripture.objects.prefetch_related(
        Prefetch(
            "indexing_jobs",
            queryset=IndexingJob.objects.filter(
                status__in=[IndexingJob.Status.PENDING, IndexingJob.Status.RUNNING]
            ),
            to_attr="active_indexing_jobs",
        )
    )
    serializer_class = ScriptureSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def reindex(self, request: Request, pk: int | None = None) -> Response:
        """Queue a staff-authorized reindex and return its durable job record."""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff users may index scriptures."},
                status=status.HTTP_403_FORBIDDEN,
            )
        scripture = self.get_object()
        active = IndexingJob.objects.filter(
            scripture=scripture,
            status__in=[IndexingJob.Status.PENDING, IndexingJob.Status.RUNNING],
        ).first()
        if active:
            return Response(
                IndexingJobSerializer(active).data, status=status.HTTP_202_ACCEPTED
            )
        job = IndexingJob.objects.create(scripture=scripture, requested_by=request.user)
        transaction.on_commit(lambda: index_scripture.delay(job.pk))
        return Response(
            IndexingJobSerializer(job).data, status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=["get"])
    def versions(self, request: Request, pk: int | None = None) -> Response:
        scripture = self.get_object()
        versions = scripture.index_versions.exclude(
            status=ScriptureIndexVersion.Status.BUILDING
        ).order_by("-created_at")[:10]
        return Response(ScriptureIndexVersionSerializer(versions, many=True).data)

    @action(detail=True, methods=["post"])
    def rollback(self, request: Request, pk: int | None = None) -> Response:
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff users may roll back scripture indexes."},
                status=status.HTTP_403_FORBIDDEN,
            )
        scripture = self.get_object()
        version_id = request.data.get("version_id")
        try:
            target = scripture.index_versions.get(
                pk=version_id,
                status__in=[
                    ScriptureIndexVersion.Status.ACTIVE,
                    ScriptureIndexVersion.Status.RETIRED,
                ],
            )
        except ScriptureIndexVersion.DoesNotExist, ValueError, TypeError:
            return Response(
                {"detail": "index_version_unavailable"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not DocumentChunk.objects.filter(index_version=target.pk).exists():
            return Response(
                {"detail": "index_version_chunks_missing"},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            locked = Scripture.objects.select_for_update().get(pk=scripture.pk)
            if (
                locked.active_index_version_id
                and locked.active_index_version_id != target.pk
            ):
                ScriptureIndexVersion.objects.filter(
                    pk=locked.active_index_version_id
                ).update(status=ScriptureIndexVersion.Status.RETIRED)
            target.status = ScriptureIndexVersion.Status.ACTIVE
            target.activated_at = timezone.now()
            target.save(update_fields=["status", "activated_at"])
            locked.active_index_version = target
            locked.is_indexed = True
            locked.last_indexed_at = timezone.now()
            locked.save(
                update_fields=[
                    "active_index_version",
                    "is_indexed",
                    "last_indexed_at",
                ]
            )
        return Response(ScriptureIndexVersionSerializer(target).data)

    def get_throttles(self):
        if getattr(self, "action", None) in {"reindex", "rollback"}:
            self.throttle_scope = "indexing"
            return [ScopedRateThrottle()]
        return super().get_throttles()


class IndexingJobViewSet(viewsets.ReadOnlyModelViewSet):
    """Staff-only observability endpoint for index job progress and failures."""

    serializer_class = IndexingJobSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return IndexingJob.objects.select_related("scripture").all()
