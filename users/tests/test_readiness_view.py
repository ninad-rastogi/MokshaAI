"""Tests for readiness dependency checks."""

from typing import Any, cast
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from users.views import ReadinessCheckView


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, sql: str) -> None:
        assert sql == "SELECT 1"


def _request():
    request = APIRequestFactory().get("/api/auth/ready/")
    cast(Any, request).user = AnonymousUser()
    return request


@override_settings(
    CELERY_BROKER_URL="redis://redis:6379/0",
    OLLAMA_BASE_URL="http://ollama:11434",
    EMBEDDING_SERVICE_URL="http://embedding:8010",
    DATA_DIR="data",
    DISK_MIN_FREE_BYTES=1,
)
def test_readiness_returns_ready_when_dependencies_pass():
    session = Mock()
    session.get.return_value.ok = True
    usage = Mock(free=1024)

    with (
        patch("users.views.connection.cursor", return_value=_Cursor()),
        patch("users.views.Redis.from_url") as redis_from_url,
        patch("users.views.requests.Session", return_value=session),
        patch("users.views.shutil.disk_usage", return_value=usage),
    ):
        response = ReadinessCheckView.as_view()(_request())

    assert response.status_code == 200
    assert response.data == {
        "status": "ready",
        "database": True,
        "redis": True,
        "ollama": True,
        "embedding": True,
        "disk": True,
    }
    redis_from_url.assert_called_once_with(
        "redis://redis:6379/0",
        socket_connect_timeout=1,
    )
    assert session.trust_env is False
    assert session.get.call_count == 2
    session.close.assert_called_once()


@override_settings(
    CELERY_BROKER_URL="redis://redis:6379/0",
    OLLAMA_BASE_URL="http://ollama:11434",
    EMBEDDING_SERVICE_URL="http://embedding:8010",
    DATA_DIR="data",
    DISK_MIN_FREE_BYTES=1,
)
def test_readiness_returns_unavailable_when_dependency_fails():
    session = Mock()
    session.get.side_effect = [Mock(ok=False), Mock(ok=True)]
    usage = Mock(free=1024)

    with (
        patch("users.views.connection.cursor", return_value=_Cursor()),
        patch("users.views.Redis.from_url"),
        patch("users.views.requests.Session", return_value=session),
        patch("users.views.shutil.disk_usage", return_value=usage),
    ):
        response = ReadinessCheckView.as_view()(_request())

    assert response.status_code == 503
    assert response.data["status"] == "unavailable"
    assert response.data["ollama"] is False
    assert response.data["embedding"] is True
