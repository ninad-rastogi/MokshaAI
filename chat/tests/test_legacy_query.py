"""Tests for removed synchronous chat query behavior."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID

from rest_framework.test import APIRequestFactory

from chat.views import ChatViewSet


def test_legacy_query_endpoint_requires_durable_generation_runs():
    request = APIRequestFactory().post(
        "/api/v1/chats/00000000-0000-0000-0000-000000000001/query/",
        {"message": "What is dharma?"},
        format="json",
    )
    cast(Any, request).user = SimpleNamespace(is_authenticated=True)
    view = ChatViewSet()

    with patch("chat.views.get_object_or_404", return_value=object()):
        response = cast(Any, view.query)(
            request,
            pk=UUID("00000000-0000-0000-0000-000000000001"),
        )

    assert response.status_code == 410
    assert response.data == {
        "error": "legacy_query_removed",
        "detail": "Create a generation run at /api/v1/chats/{id}/runs/.",
    }
