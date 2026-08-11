"""Tests for chat API throttle scopes."""

from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import ScopedRateThrottle

from chat.views import ChatViewSet
from users.models import User


def test_generation_run_creation_uses_chat_query_throttle_scope():
    view = ChatViewSet()
    view.action = "runs"

    throttles = view.get_throttles()

    assert len(throttles) == 1
    assert isinstance(throttles[0], ScopedRateThrottle)
    assert view.throttle_scope == "chat_query"


@pytest.mark.django_db
def test_discover_endpoint_queues_auto_discovery():
    request = APIRequestFactory().post("/api/v1/chats/discover/")
    user = User.objects.create_user(
        email="discover@example.test",
        password="StrongPass123!",
    )
    force_authenticate(request, user=user)
    view = ChatViewSet.as_view({"post": "discover"})

    with patch("moksha.tasks.auto_discover_scripture_indexes.delay") as delay:
        delay.return_value.id = "task-123"
        response = view(request)

    assert response.status_code == 200
    assert response.data == {
        "status": "discovery_queued",
        "task_id": "task-123",
    }
    delay.assert_called_once_with()
