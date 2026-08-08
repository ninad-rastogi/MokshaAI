"""Tests for provider probes and model selection precedence."""

import json
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from llm.models import ModelConnection, ModelProfile, UserModelPreference
from llm.providers import (
    ProviderRequestFailed,
    ollama_chat_completion,
    openai_chat_completion,
    probe_connection,
    update_connection_probe,
)
from llm.services import resolve_model_selection
from users.models import User


@pytest.mark.django_db
def test_resolve_model_selection_uses_override_then_user_then_admin_default() -> None:
    user = User.objects.create_user(email="models@example.test", password="pass")
    ModelProfile.objects.filter(is_admin_default=True).update(is_admin_default=False)
    admin_connection = ModelConnection.objects.create(
        name="Built-in Ollama",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    admin_default = ModelProfile.objects.create(
        name="Admin Local",
        connection=admin_connection,
        model_id="moksha-local",
        is_enabled=True,
        is_admin_default=True,
    )
    user_primary = ModelProfile.objects.create(
        name="User Primary",
        connection=admin_connection,
        model_id="user-primary",
        is_enabled=True,
    )
    override = ModelProfile.objects.create(
        name="Chat Override",
        connection=admin_connection,
        model_id="chat-override",
        is_enabled=True,
    )
    UserModelPreference.objects.create(
        user=user,
        primary_profile=user_primary,
        ordered_fallback_profile_ids=[str(admin_default.pk)],
    )

    selection = resolve_model_selection(
        user=user,
        chat_override_profile_id=str(override.pk),
    )
    assert selection.primary == override
    assert selection.fallback == user_primary


@pytest.mark.django_db
def test_resolve_model_selection_falls_back_to_admin_default() -> None:
    user = User.objects.create_user(email="default@example.test", password="pass")
    ModelProfile.objects.filter(is_admin_default=True).update(is_admin_default=False)
    connection = ModelConnection.objects.create(
        name="Built-in Ollama",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    profile = ModelProfile.objects.create(
        name="Admin Default",
        connection=connection,
        model_id="default-model",
        is_enabled=True,
        is_admin_default=True,
    )
    selection = resolve_model_selection(user=user)
    assert selection.primary == profile
    assert selection.fallback is None


def test_probe_connection_rejects_unsafe_endpoint() -> None:
    connection = ModelConnection(
        name="Localhost",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://localhost:11434",
        dns_pins=["127.0.0.1"],
    )
    result = probe_connection(connection)
    assert result.status == ModelConnection.Status.ENDPOINT_INVALID
    assert "localhost" not in result.detail.lower()


def test_probe_connection_maps_openai_models_success(settings) -> None:
    connection = ModelConnection(
        name="OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
    )

    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(
        {"data": [{"id": "alpha"}, {"id": "beta"}]}
    ).encode("utf-8")
    fake_http = Mock()
    fake_http.getresponse.return_value = response

    with patch(
        "llm.providers.NoRedirectHTTPSConnection",
        return_value=fake_http,
    ) as connection_class:
        result = probe_connection(connection)

    assert result.status == ModelConnection.Status.CONNECTED
    assert result.models == ("alpha", "beta")
    fake_http.request.assert_called_once()
    _, path = fake_http.request.call_args.args[:2]
    assert path == "/v1/models"
    assert connection_class.call_args.args[:2] == (
        "api.example.com",
        "93.184.216.34",
    )


def test_probe_connection_sanitizes_http_failure() -> None:
    connection = ModelConnection(
        name="OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
    )
    response = Mock()
    response.status = 401
    response.read.return_value = b'{"error":"secret leaked"}'
    fake_http = Mock()
    fake_http.getresponse.return_value = response

    with patch("llm.providers.NoRedirectHTTPSConnection", return_value=fake_http):
        result = probe_connection(connection)

    assert result.status == ModelConnection.Status.AUTH_INVALID
    assert "secret" not in result.detail


def test_provider_request_failed_maps_quota_status() -> None:
    failure = ProviderRequestFailed(402)

    assert failure.code == ModelConnection.Status.QUOTA_LIMITED
    assert "402" not in str(failure)


@pytest.mark.django_db
def test_openai_chat_completion_posts_safe_payload(settings) -> None:
    settings.BYOK_MASTER_KEY = ""
    connection = ModelConnection.objects.create(
        name="OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        remote_data_consent_at=timezone.now(),
    )
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(
        {
            "choices": [{"message": {"content": "Remote answer."}}],
            "usage": {"total_tokens": 12},
        }
    ).encode("utf-8")
    fake_http = Mock()
    fake_http.getresponse.return_value = response

    with patch("llm.providers.NoRedirectHTTPSConnection", return_value=fake_http):
        text, usage = openai_chat_completion(
            connection=connection,
            model="remote-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.2,
            max_output_tokens=128,
        )

    assert text == "Remote answer."
    assert usage == {"total_tokens": 12}
    method, path = fake_http.request.call_args.args[:2]
    assert method == "POST"
    assert path == "/v1/chat/completions"
    headers = fake_http.request.call_args.kwargs["headers"]
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_openai_chat_completion_streams_deltas(settings) -> None:
    settings.BYOK_MASTER_KEY = ""
    connection = ModelConnection.objects.create(
        name="Streaming OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        remote_data_consent_at=timezone.now(),
    )
    response = Mock()
    response.status = 200
    response.readline.side_effect = [
        b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n',
        b'data: {"choices":[{"delta":{"content":"there"}}]}\n',
        b'data: {"choices":[],"usage":{"total_tokens":5}}\n',
        b"data: [DONE]\n",
    ]
    fake_http = Mock()
    fake_http.getresponse.return_value = response
    deltas: list[str] = []

    with patch("llm.providers.NoRedirectHTTPSConnection", return_value=fake_http):
        text, usage = openai_chat_completion(
            connection=connection,
            model="remote-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.2,
            max_output_tokens=128,
            on_delta=deltas.append,
        )

    assert text == "Hello there"
    assert deltas == ["Hello ", "there"]
    assert usage == {"total_tokens": 5}
    body = fake_http.request.call_args.kwargs["body"]
    payload = json.loads(body.decode("utf-8"))
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}


@pytest.mark.django_db
def test_openai_chat_completion_rejects_crlf_api_key(settings) -> None:
    settings.BYOK_MASTER_KEY = ""
    user = User.objects.create_user(email="crlf@example.test", password="pass")
    connection = ModelConnection.objects.create(
        user=user,
        name="OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        remote_data_consent_at=timezone.now(),
        encrypted_api_key="not-used",
        api_key_nonce="not-used",
    )
    with (
        patch.object(connection, "get_api_key", return_value="sk-test\r\nbad: x"),
        pytest.raises(Exception),
    ):
        openai_chat_completion(
            connection=connection,
            model="remote-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.2,
            max_output_tokens=128,
        )


@pytest.mark.django_db
def test_ollama_chat_completion_posts_safe_payload() -> None:
    connection = ModelConnection.objects.create(
        name="Ollama Compatible",
        dialect=ModelConnection.Dialect.OLLAMA_COMPATIBLE,
        endpoint_url="https://ollama.example.com",
        dns_pins=["93.184.216.34"],
        remote_data_consent_at=timezone.now(),
    )
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(
        {
            "message": {"content": "Ollama answer."},
            "prompt_eval_count": 4,
            "eval_count": 8,
        }
    ).encode("utf-8")
    fake_http = Mock()
    fake_http.getresponse.return_value = response

    with patch("llm.providers.NoRedirectHTTPSConnection", return_value=fake_http):
        text, usage = ollama_chat_completion(
            connection=connection,
            model="remote-ollama",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.2,
            max_output_tokens=128,
        )

    assert text == "Ollama answer."
    assert usage == {"prompt_eval_count": 4, "eval_count": 8}
    method, path = fake_http.request.call_args.args[:2]
    assert method == "POST"
    assert path == "/api/chat"
    body = fake_http.request.call_args.kwargs["body"]
    assert json.loads(body.decode("utf-8"))["options"]["num_predict"] == 128


@pytest.mark.django_db
def test_update_connection_probe_persists_status_without_secret_detail() -> None:
    connection = ModelConnection.objects.create(
        name="OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        remote_data_consent_at=timezone.now(),
    )
    with patch(
        "llm.providers.probe_connection",
        return_value=Mock(
            status=ModelConnection.Status.RATE_LIMITED,
            detail="Provider returned HTTP 429.",
            models=(),
        ),
    ):
        update_connection_probe(connection)
    connection.refresh_from_db()
    assert connection.status == ModelConnection.Status.RATE_LIMITED
    assert connection.sanitized_detail == "Provider returned HTTP 429."
