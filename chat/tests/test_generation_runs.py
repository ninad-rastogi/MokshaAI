"""Tests for durable generation run API behavior."""

from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from django.urls import Resolver404, resolve

from chat.models import Chat, GenerationAttempt, GenerationRun, Message
from chat.tasks import generate_chat_response
from llm.models import ModelConnection, ModelProfile
from llm.providers import ProviderRequestFailed


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


def test_legacy_query_url_is_not_part_of_v1_contract():
    with pytest.raises(Resolver404):
        resolve("/api/v1/chats/00000000-0000-0000-0000-000000000001/query/")


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
    with patch("chat.views.publish_run_event", side_effect=["1-0", "2-0"]):
        cancelled = client.post(f"/api/v1/runs/{run.id}/cancel/")

    assert detail.status_code == 200
    assert detail.json()["id"] == str(run.id)
    assert events.status_code == 200
    assert events["Content-Type"].startswith("text/event-stream")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == GenerationRun.State.CANCELLED
    assert cancelled.json()["last_event_id"] == "2-0"


@pytest.mark.django_db
def test_generation_run_uses_legacy_model_when_no_profiles(create_user):
    ModelProfile.objects.all().delete()
    ModelConnection.objects.all().delete()
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
    ModelProfile.objects.filter(is_admin_default=True).update(is_admin_default=False)
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

    emitted_events: list[str] = []

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
def test_generation_run_replaces_invented_source_claim(create_user):
    user = create_user(email="grounding-guard@example.test")
    ModelProfile.objects.filter(is_admin_default=True).update(is_admin_default=False)
    chat = Chat.objects.create(user=user)
    connection = ModelConnection.objects.create(
        name="Built-in Ollama guard",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    profile = ModelProfile.objects.create(
        name="Guarded Profile",
        connection=connection,
        model_id="guard-model",
        is_enabled=True,
        is_admin_default=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="grounding-guard",
        prompt="How can I act without resentment?",
        model_profile=str(profile.pk),
        stream_key=f"generation:{chat.id}:grounding-guard",
    )
    sources = [
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "excerpt": "Exact source passage.",
        }
    ]

    def fake_generate(**_kwargs):
        return (
            "Fake answer. (From The Book of Life, File: Wisdom, Page 34)",
            sources,
            "RAG",
        )

    emitted_events: list[tuple[str, dict[str, Any]]] = []

    def fake_publish(_stream_key, event_type, payload):
        emitted_events.append((event_type, payload))
        return f"{len(emitted_events)}-0"

    with (
        patch("chat.tasks.resolve_model_selection") as resolve,
        patch("chat.tasks.publish_run_event", side_effect=fake_publish),
        patch("chat.tasks._generate_response", side_effect=fake_generate),
    ):
        resolve.return_value.attempts = (profile,)
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    message = Message.objects.get(chat=chat, role="assistant")
    delta_payloads = [
        payload["text"]
        for event_type, payload in emitted_events
        if event_type == "delta"
    ]
    assert run.state == GenerationRun.State.COMPLETED
    assert "The Book of Life" not in message.content
    assert "Exact source passage." in message.content
    assert all("The Book of Life" not in payload for payload in delta_payloads)


@pytest.mark.django_db
def test_generation_run_does_not_fallback_after_first_delta(create_user):
    user = create_user(email="no-late-fallback@example.test")
    ModelProfile.objects.filter(is_admin_default=True).update(is_admin_default=False)
    chat = Chat.objects.create(user=user)
    connection = ModelConnection.objects.create(
        name="Built-in Ollama stream",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    primary = ModelProfile.objects.create(
        name="Streaming primary",
        connection=connection,
        model_id="stream-primary",
        is_enabled=True,
        is_admin_default=True,
    )
    fallback = ModelProfile.objects.create(
        name="Streaming fallback",
        connection=connection,
        model_id="stream-fallback",
        is_enabled=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="no-late-fallback",
        prompt="Please guide me.",
        model_profile=str(primary.pk),
        stream_key=f"generation:{chat.id}:no-late-fallback",
    )

    def fake_generate(**kwargs):
        kwargs["on_delta"]("Partial answer")
        raise RuntimeError("stream interrupted")

    with (
        patch("chat.tasks.resolve_model_selection") as resolve,
        patch("chat.tasks.publish_run_event", return_value="1-0"),
        patch("chat.tasks._generate_response", side_effect=fake_generate),
    ):
        resolve.return_value.attempts = (primary, fallback)
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempts = list(run.attempts.order_by("attempt_number"))
    assert run.state == GenerationRun.State.FAILED
    assert run.final_text == "Partial answer"
    assert [attempt.model for attempt in attempts] == ["stream-primary"]
    assert attempts[0].outcome == GenerationAttempt.Outcome.FAILED
    assert not Message.objects.filter(chat=chat, role="assistant").exists()


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

    emitted_events: list[tuple[str, str, dict[str, Any]]] = []

    def fake_publish(_stream_key, event_type, payload):
        event_id = f"{len(emitted_events) + 1}-0"
        emitted_events.append((event_id, event_type, payload))
        return event_id

    with (
        patch("chat.tasks.publish_run_event", side_effect=fake_publish),
        patch(
            "chat.tasks.openai_chat_completion",
            return_value=("Remote answer.", {"total_tokens": 9}),
        ) as remote,
    ):
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempt = run.attempts.get()
    usage_event = next(event for event in emitted_events if event[1] == "usage")
    done_event = next(event for event in emitted_events if event[1] == "done")
    assert run.state == GenerationRun.State.COMPLETED
    assert run.last_event_id == done_event[0]
    assert attempt.provider == ModelConnection.Dialect.OPENAI_COMPATIBLE
    assert attempt.model == "remote-model"
    assert attempt.usage == {"total_tokens": 9}
    assert usage_event[2] == {
        "attempt_number": 1,
        "provider": ModelConnection.Dialect.OPENAI_COMPATIBLE,
        "model": "remote-model",
        "usage": {"total_tokens": 9},
        "warnings": [],
    }
    assert [event[1] for event in emitted_events].index("usage") < [
        event[1] for event in emitted_events
    ].index("done")
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


@pytest.mark.django_db
def test_generation_run_persists_sanitized_provider_error_before_fallback(create_user):
    user = create_user(email="remote-error-code@example.test")
    chat = Chat.objects.create(user=user)
    connection = ModelConnection.objects.create(
        user=user,
        name="Remote",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        status=ModelConnection.Status.CONNECTED,
    )
    primary = ModelProfile.objects.create(
        name="Remote Primary",
        connection=connection,
        model_id="remote-primary",
        is_enabled=True,
    )
    fallback = ModelProfile.objects.create(
        name="Remote Fallback",
        connection=connection,
        model_id="remote-fallback",
        is_enabled=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="remote-error-code",
        prompt="Offer brief guidance.",
        model_profile=str(primary.pk),
        stream_key=f"generation:{chat.id}:remote-error-code",
    )

    def fake_generate(**kwargs):
        if kwargs["spec"].model == "remote-primary":
            raise ProviderRequestFailed(429)
        return "Fallback answer.", [], "GENERAL"

    emitted_events: list[tuple[str, dict[str, Any]]] = []

    def fake_publish(_stream_key, event_type, payload):
        emitted_events.append((event_type, payload))
        return f"{len(emitted_events)}-0"

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
    assert attempts[0].outcome == GenerationAttempt.Outcome.FAILED
    assert attempts[0].error_code == ModelConnection.Status.RATE_LIMITED
    assert attempts[1].outcome == GenerationAttempt.Outcome.SUCCEEDED
    assert attempts[1].error_code == ""
    usage_payload = next(
        payload for event_type, payload in emitted_events if event_type == "usage"
    )
    assert usage_payload["warnings"] == [
        "A failed remote provider attempt may still be billed by that provider."
    ]


@pytest.mark.django_db
def test_generation_run_emits_sanitized_provider_error(create_user):
    user = create_user(email="remote-quota-error@example.test")
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
        name="Remote Primary",
        connection=connection,
        model_id="remote-primary",
        is_enabled=True,
    )
    run = GenerationRun.objects.create(
        chat=chat,
        user=user,
        idempotency_key="remote-quota-error",
        prompt="Offer brief guidance.",
        model_profile=str(profile.pk),
        stream_key=f"generation:{chat.id}:remote-quota-error",
    )
    emitted_events: list[tuple[str, dict[str, Any]]] = []

    def fake_publish(_stream_key, event_type, payload):
        emitted_events.append((event_type, payload))
        return f"{len(emitted_events)}-0"

    with (
        patch("chat.tasks.resolve_model_selection") as resolve,
        patch("chat.tasks.publish_run_event", side_effect=fake_publish),
        patch("chat.tasks._generate_response", side_effect=ProviderRequestFailed(402)),
    ):
        resolve.return_value.attempts = (profile,)
        generate_chat_response(str(run.pk))

    run.refresh_from_db()
    attempt = run.attempts.get()
    error_payload = next(
        payload for event, payload in emitted_events if event == "error"
    )
    assert run.state == GenerationRun.State.FAILED
    assert run.error_code == ModelConnection.Status.QUOTA_LIMITED
    assert attempt.outcome == GenerationAttempt.Outcome.FAILED
    assert attempt.error_code == ModelConnection.Status.QUOTA_LIMITED
    assert error_payload["code"] == ModelConnection.Status.QUOTA_LIMITED
    assert (
        error_payload["warning"]
        == "A failed remote provider attempt may still be billed by that provider."
    )
    assert "402" not in error_payload["message"]
