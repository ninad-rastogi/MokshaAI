"""Views for model profiles, connections, and user routing preferences."""

from typing import cast

from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from llm.models import ModelConnection, ModelProfile, UserModelPreference
from llm.serializers import (
    ModelConnectionSerializer,
    ModelProfileSerializer,
    UserModelPreferenceSerializer,
)
from users.models import User


class ModelConnectionViewSet(viewsets.ReadOnlyModelViewSet):
    """Read sanitized provider connection status for the current user."""

    serializer_class = ModelConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = cast(User, self.request.user)
        return ModelConnection.objects.filter(Q(user=user) | Q(user=None))


class ModelProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """List selectable enabled model profiles."""

    serializer_class = ModelProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ModelProfile.objects.filter(is_enabled=True).select_related("connection")


class UserModelPreferenceViewSet(viewsets.ViewSet):
    """Get or update the authenticated user's model preference."""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get", "put"], url_path="me")
    def me(self, request: Request) -> Response:
        user = cast(User, request.user)
        preference, _ = UserModelPreference.objects.get_or_create(user=user)
        if request.method == "GET":
            return Response(UserModelPreferenceSerializer(preference).data)
        serializer = UserModelPreferenceSerializer(preference, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        return Response(serializer.data)
