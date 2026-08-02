"""Views for model profiles, connections, and user routing preferences."""

from typing import cast

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from llm.catalog import CatalogValidationError, activate_configured_catalog
from llm.models import (
    ModelCatalogRelease,
    ModelConnection,
    ModelInstallationJob,
    ModelProfile,
    UserModelPreference,
)
from llm.providers import update_connection_probe
from llm.serializers import (
    ModelCatalogReleaseSerializer,
    ModelConnectionCreateSerializer,
    ModelConnectionProbeSerializer,
    ModelConnectionSerializer,
    ModelInstallationCreateSerializer,
    ModelInstallationJobSerializer,
    ModelProfileSerializer,
    UserModelPreferenceSerializer,
)
from users.models import User


class ModelConnectionViewSet(viewsets.ModelViewSet):
    """Read sanitized provider connection status for the current user."""

    serializer_class = ModelConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        user = cast(User, self.request.user)
        return ModelConnection.objects.filter(Q(user=user) | Q(user=None))

    def get_serializer_class(self):
        if self.action == "create":
            return ModelConnectionCreateSerializer
        return ModelConnectionSerializer

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        return Response(
            ModelConnectionSerializer(connection).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        connection = self.get_object()
        user = cast(User, request.user)
        if connection.user_id != user.pk:
            return Response(
                {"detail": "connection_delete_forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            profile_ids = [
                str(profile_id)
                for profile_id in connection.profiles.values_list("id", flat=True)
            ]
            preferences = UserModelPreference.objects.filter(user=user)
            for preference in preferences.select_for_update():
                if str(preference.primary_profile_id) in profile_ids:
                    preference.primary_profile = None
                preference.ordered_fallback_profile_ids = [
                    profile_id
                    for profile_id in preference.ordered_fallback_profile_ids
                    if str(profile_id) not in profile_ids
                ]
                preference.save(
                    update_fields=[
                        "primary_profile",
                        "ordered_fallback_profile_ids",
                        "updated_at",
                    ]
                )
            connection.profiles.all().delete()
            connection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def probe(self, request: Request, pk: str | None = None) -> Response:
        connection = self.get_object()
        user = cast(User, request.user)
        if connection.user_id is None and not user.is_staff:
            return Response(
                {"detail": "admin_connection_probe_forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if connection.user_id is not None and connection.user_id != user.pk:
            return Response(
                {"detail": "connection_probe_forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        result = update_connection_probe(connection)
        serializer = ModelConnectionProbeSerializer(
            {"status": result.status, "detail": result.detail, "models": result.models}
        )
        http_status = (
            status.HTTP_200_OK
            if result.status == ModelConnection.Status.CONNECTED
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(serializer.data, status=http_status)


class ModelProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """List selectable enabled model profiles."""

    serializer_class = ModelProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = cast(User, self.request.user)
        return ModelProfile.objects.filter(
            Q(connection__user=user) | Q(connection__user=None),
            is_enabled=True,
        ).select_related("connection")


class UserModelPreferenceViewSet(viewsets.ViewSet):
    """Get or update the authenticated user's model preference."""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get", "put"], url_path="me")
    def me(self, request: Request) -> Response:
        user = cast(User, request.user)
        preference, _ = UserModelPreference.objects.get_or_create(user=user)
        if request.method == "GET":
            return Response(UserModelPreferenceSerializer(preference).data)
        serializer = UserModelPreferenceSerializer(
            preference,
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        return Response(serializer.data)


class ModelCatalogViewSet(viewsets.ViewSet):
    """Read active catalog metadata and allow staff-only file refresh."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        release = ModelCatalogRelease.objects.filter(active=True).first()
        if release is None:
            return Response(
                {"detail": "catalog_not_loaded"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ModelCatalogReleaseSerializer(release).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAdminUser],
    )
    def refresh(self, request: Request) -> Response:
        try:
            release = activate_configured_catalog()
        except CatalogValidationError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            ModelCatalogReleaseSerializer(release).data,
            status=status.HTTP_201_CREATED,
        )


class ModelInstallationJobViewSet(viewsets.ReadOnlyModelViewSet):
    """Create and inspect one-at-a-time staff local installation jobs."""

    serializer_class = ModelInstallationJobSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = ModelInstallationJob.objects.select_related(
        "created_by",
        "model_profile",
    )

    def get_serializer_class(self):
        if self.action == "create":
            return ModelInstallationCreateSerializer
        return ModelInstallationJobSerializer

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = cast(User, request.user)
        release = ModelCatalogRelease.objects.filter(active=True).first()
        if release is None:
            return Response(
                {"detail": "catalog_not_loaded"},
                status=status.HTTP_409_CONFLICT,
            )
        active = ModelInstallationJob.objects.filter(
            status__in=[
                ModelInstallationJob.Status.PENDING,
                ModelInstallationJob.Status.RUNNING,
            ]
        ).first()
        if active is not None:
            return Response(
                ModelInstallationJobSerializer(active).data,
                status=status.HTTP_409_CONFLICT,
            )
        entry_id = serializer.validated_data["entry_id"]
        entries = release.payload.get("entries", [])
        entry = next(
            (
                item
                for item in entries
                if isinstance(item, dict) and item.get("id") == entry_id
            ),
            None,
        )
        if entry is None:
            return Response(
                {"detail": "catalog_entry_unavailable"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        snapshot = {**entry, "_catalog_version": release.version}
        try:
            with transaction.atomic():
                job = ModelInstallationJob.objects.create(
                    created_by=user,
                    catalog_entry=snapshot,
                    source_sha256=entry["sha256"],
                    source_size=entry["size"],
                    keep_source=serializer.validated_data["keep_source"],
                )
                from llm.tasks import install_local_model

                transaction.on_commit(lambda: install_local_model.delay(str(job.pk)))
        except IntegrityError:
            active = ModelInstallationJob.objects.filter(
                status__in=[
                    ModelInstallationJob.Status.PENDING,
                    ModelInstallationJob.Status.RUNNING,
                ]
            ).first()
            return Response(
                ModelInstallationJobSerializer(active).data,
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            ModelInstallationJobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        job = self.get_object()
        changed = ModelInstallationJob.objects.filter(
            pk=job.pk,
            status=ModelInstallationJob.Status.PENDING,
        ).update(
            status=ModelInstallationJob.Status.CANCELLED,
            active_lock=False,
            finished_at=timezone.now(),
        )
        if not changed:
            return Response(
                {"detail": "installation_cannot_be_cancelled"},
                status=status.HTTP_409_CONFLICT,
            )
        job.refresh_from_db()
        return Response(ModelInstallationJobSerializer(job).data)
