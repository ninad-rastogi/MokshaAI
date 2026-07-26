"""Tests for durable generation run API behavior."""

from unittest.mock import patch

import pytest

from chat.models import Chat, GenerationAttempt, GenerationRun, Message
from llm.models import ModelConnection, ModelProfile
from chat.tasks import generate_chat_response


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


@pytest.mark.django_db
def test_generation_run_uses_legacy_model_when_no_profiles(create_user):
    user = create_user(email="legacy-run@example.test")
    chat = Chat.objects.create(user=user)
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="legacy",
        prompt="What is steadiness?",
        stream_key=f"generation:{chat.id}:legacy",
    )

    with (
        patch("chat.tasks.publish_run_event", return_value="1-0"),
        patch(
            "chat.tasks._generate_response",
            return_value=("Steadiness is practice.", [], "GENERAL"),
        ) as generate,
    ):
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempt = run.attempts.get()
    assert run.state == GenerationRun.State.COMPLETED
    assert attempt.provider == "ollama"
    assert attempt.outcome == GenerationAttempt.Outcome.SUCCEEDED
    assert attempt.model_snapshot["legacy"] is True
    assert generate.call_count == 1
    assert Message.objects.filter(chat=chat, role="assistant").count() == 1


@pytest.mark.django_db
def test_generation_run_falls_back_before_delta(create_user):
    user = create_user(email="fallback-run@example.test")
    chat = Chat.objects.create(user=user)
    connection = ModelConnection.objects.create(
        name="Built-in Ollama",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    primary = ModelProfile.objects.create(
        name="Primary",
        connection=connection,
        model_id="primary-model",
        is_enabled=True,
        is_admin_default=True,
    )
    fallback = ModelProfile.objects.create(
        name="Fallback",
        connection=connection,
        model_id="fallback-model",
        is_enabled=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="fallback",
        prompt="What is dharma?",
        model_profile=str(primary.pk),
        stream_key=f"generation:{chat.id}:fallback",
    )

    emitted_events = []

    def fake_publish(_stream_key, event_type, _payload):
        emitted_events.append(event_type)
        return f"{len(emitted_events)}-0"

    def fake_generate(**kwargs):
        spec = kwargs["spec"]
        if spec.model == "primary-model":
            raise RuntimeError("primary failed")
        assert spec.model == "fallback-model"
        return "Fallback answer.", [], "GENERAL"

    with (
        patch("chat.tasks.resolve_model_selection") as resolve,
        patch("chat.tasks.publish_run_event", side_effect=fake_publish),
        patch("chat.tasks._generate_response", side_effect=fake_generate),
    ):
        resolve.return_value.attempts = (primary, fallback)
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempts = list(run.attempts.order_by("attempt_number"))
    assert run.state == GenerationRun.State.COMPLETED
    assert [attempt.model for attempt in attempts] == [
        "primary-model",
        "fallback-model",
    ]
    assert attempts[0].outcome == GenerationAttempt.Outcome.FAILED
    assert attempts[1].outcome == GenerationAttempt.Outcome.SUCCEEDED
    assert "delta" in emitted_events
    assert emitted_events.index("delta") > emitted_events.index("state")
    assert Message.objects.filter(chat=chat, role="assistant").count() == 1
