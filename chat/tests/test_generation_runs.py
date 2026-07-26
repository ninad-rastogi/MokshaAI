"""Tests for durable generation run API behavior."""

from unittest.mock import patch
from uuid import UUID

from django.urls import resolve
import pytest

from chat.models import Chat, GenerationAttempt, GenerationRun, Message
from llm.models import ModelConnection, ModelProfile
from chat.tasks import generate_chat_response


def test_top_level_run_urls_resolve_to_v1_contract():
    run_id = UUID("00000000-0000-0000-0000-000000000001")

    detail = resolve(f"/api/v1/runs/{run_id}/")
    events = resolve(f"/api/v1/runs/{run_id}/events/")
    cancel = resolve(f"/api/v1/runs/{run_id}/cancel/")

    assert detail.url_name == "generation-run-detail"
    assert detail.kwargs["pk"] == run_id
    assert events.url_name == "generation-run-events"
    assert events.kwargs["pk"] == run_id
    assert cancel.url_name == "generation-run-cancel"
    assert cancel.kwargs["pk"] == run_id


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
def test_top_level_run_endpoints_match_v1_contract(authenticated_client):
    client, user = authenticated_client
    chat = Chat.objects.create(user=user)
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="top-level",
        prompt="Please answer",
        stream_key=f"generation:{chat.id}:top-level",
    )

    detail = client.get(f"/api/v1/runs/{run.id}/")
    events = client.get(f"/api/v1/runs/{run.id}/events/")
    with patch("chat.views.publish_run_event", return_value="1-0"):
        cancelled = client.post(f"/api/v1/runs/{run.id}/cancel/")

    assert detail.status_code == 200
    assert detail.json()["id"] == str(run.id)
    assert events.status_code == 200
    assert events["Content-Type"].startswith("text/event-stream")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == GenerationRun.State.CANCELLED


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


@pytest.mark.django_db
def test_generation_run_openai_profile_persists_usage(create_user):
    user = create_user(email="remote-run@example.test")
    chat = Chat.objects.create(user=user)
    connection = ModelConnection.objects.create(
        user=user,
        name="Remote",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        status=ModelConnection.Status.CONNECTED,
    )
    profile = ModelProfile.objects.create(
        name="Remote Profile",
        connection=connection,
        model_id="remote-model",
        is_enabled=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="remote",
        prompt="Offer brief guidance.",
        model_profile=str(profile.pk),
        stream_key=f"generation:{chat.id}:remote",
    )

    with (
        patch("chat.tasks.publish_run_event", return_value="1-0"),
        patch(
            "chat.tasks.openai_chat_completion",
            return_value=("Remote answer.", {"total_tokens": 9}),
        ) as remote,
    ):
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempt = run.attempts.get()
    assert run.state == GenerationRun.State.COMPLETED
    assert attempt.provider == ModelConnection.Dialect.OPENAI_COMPATIBLE
    assert attempt.model == "remote-model"
    assert attempt.usage == {"total_tokens": 9}
    assert remote.call_count == 1


@pytest.mark.django_db
def test_generation_run_ollama_compatible_profile_persists_usage(create_user):
    user = create_user(email="remote-ollama-run@example.test")
    chat = Chat.objects.create(user=user)
    connection = ModelConnection.objects.create(
        user=user,
        name="Remote Ollama",
        dialect=ModelConnection.Dialect.OLLAMA_COMPATIBLE,
        endpoint_url="https://ollama.example.com",
        dns_pins=["93.184.216.34"],
        status=ModelConnection.Status.CONNECTED,
    )
    profile = ModelProfile.objects.create(
        name="Remote Ollama Profile",
        connection=connection,
        model_id="remote-ollama",
        is_enabled=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="remote-ollama",
        prompt="Offer brief guidance.",
        model_profile=str(profile.pk),
        stream_key=f"generation:{chat.id}:remote-ollama",
    )

    with (
        patch("chat.tasks.publish_run_event", return_value="1-0"),
        patch(
            "chat.tasks.ollama_chat_completion",
            return_value=("Ollama answer.", {"eval_count": 7}),
        ) as remote,
    ):
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempt = run.attempts.get()
    assert run.state == GenerationRun.State.COMPLETED
    assert attempt.provider == "ollama_compatible"
    assert attempt.model == "remote-ollama"
    assert attempt.usage == {"eval_count": 7}
    assert remote.call_count == 1
