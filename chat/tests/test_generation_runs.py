"""Tests for durable generation run API behavior."""

from unittest.mock import patch

import pytest

from chat.models import Chat, GenerationRun


@pytest.mark.django_db
def test_create_run_requires_idempotency_key(authenticated_client):
    client, user = authenticated_client
    chat = Chat.objects.create(user=user)

    response = client.post(
        f"/api/v1/chats/{chat.id}/runs/",
        {"message": "What does dharma mean?"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "idempotency_key_required"


@pytest.mark.django_db
def test_duplicate_idempotency_key_returns_existing_run(authenticated_client):
    client, user = authenticated_client
    chat = Chat.objects.create(user=user)

    with (
        patch("chat.views.generate_chat_response.delay") as delay,
        patch("chat.views.publish_run_event", return_value="1-0"),
    ):
        first = client.post(
            f"/api/v1/chats/{chat.id}/runs/",
            {"message": "What does dharma mean?"},
            HTTP_IDEMPOTENCY_KEY="run-1",
            format="json",
        )
        second = client.post(
            f"/api/v1/chats/{chat.id}/runs/",
            {"message": "What does dharma mean?"},
            HTTP_IDEMPOTENCY_KEY="run-1",
            format="json",
        )

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert delay.call_count == 1


@pytest.mark.django_db
def test_delete_chat_with_active_run_returns_conflict(authenticated_client):
    client, user = authenticated_client
    chat = Chat.objects.create(user=user)
    GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="active",
        prompt="Please answer",
        stream_key=f"generation:{chat.id}:active",
    )

    response = client.delete(f"/api/v1/chats/{chat.id}/")

    assert response.status_code == 409
    assert response.json()["error"] == "active_run"
