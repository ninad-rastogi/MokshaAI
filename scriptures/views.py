"""Views for the scriptures app."""

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from scriptures.models import IndexingJob, Scripture
from scriptures.serializers import IndexingJobSerializer, ScriptureSerializer
from scriptures.tasks import index_scripture


class ScriptureViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving scriptures."""

    queryset = Scripture.objects.all()
    serializer_class = ScriptureSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def reindex(self, request: Request, pk: int = None) -> Response:
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

    def get_throttles(self):
        if getattr(self, "action", None) == "reindex":
            self.throttle_scope = "indexing"
            return [ScopedRateThrottle()]
        return super().get_throttles()


class IndexingJobViewSet(viewsets.ReadOnlyModelViewSet):
    """Staff-only observability endpoint for index job progress and failures."""

    serializer_class = IndexingJobSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return IndexingJob.objects.select_related("scripture").all()
