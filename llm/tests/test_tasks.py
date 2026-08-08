"""Unit tests for bounded local model installation helpers."""

from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings

from llm.tasks import (
    InstallationError,
    _copy_model,
    _qualified_tag,
    _running_model_memory,
    _session,
    _validated_download_response,
)


def test_qualified_tag_is_versioned_and_safe():
    assert (
        _qualified_tag(
            {"id": "Example Model Q3_K_M"},
            "2026.07.30.1",
        )
        == "moksha-example-model-q3_k_m:2026.07.30.1"
    )


def test_installation_error_code_fails_closed():
    assert InstallationError("ollama_api_failure").code == "ollama_api_failure"
    assert (
        InstallationError("raw filesystem path D:/secret/model.gguf").code
        == "model_installation_failed"
    )


def test_download_session_ignores_proxy_environment():
    session = _session()
    try:
        assert session.trust_env is False
    finally:
        session.close()


@patch("llm.tasks.validate_public_https_endpoint")
def test_validated_download_response_handles_https_redirect_without_auto_follow(
    mock_validate,
):
    session = Mock(spec=requests.Session)
    redirect = Mock()
    redirect.status_code = 302
    redirect.headers = {"Location": "https://downloads.example.com/model.gguf"}
    final = Mock()
    final.status_code = 200
    final.headers = {}
    session.get.side_effect = [redirect, final]

    response = _validated_download_response(
        session,
        "https://catalog.example.com/model.gguf",
        offset=0,
    )

    assert response == final
    assert session.get.call_count == 2
    assert all(
        call.kwargs["allow_redirects"] is False for call in session.get.call_args_list
    )
    assert mock_validate.call_args_list[0].args == (
        "https://catalog.example.com/model.gguf",
    )
    assert mock_validate.call_args_list[1].args == (
        "https://downloads.example.com/model.gguf",
    )
    redirect.close.assert_called_once()


@patch("llm.tasks.validate_public_https_endpoint")
def test_validated_download_response_rejects_non_https_redirect(mock_validate):
    session = Mock(spec=requests.Session)
    redirect = Mock()
    redirect.status_code = 302
    redirect.headers = {"Location": "http://downloads.example.com/model.gguf"}
    session.get.return_value = redirect

    with pytest.raises(InstallationError, match="model_download_redirect_invalid"):
        _validated_download_response(
            session,
            "https://catalog.example.com/model.gguf",
            offset=0,
        )

    session.get.assert_called_once()
    redirect.close.assert_called_once()
    mock_validate.assert_called_once_with("https://catalog.example.com/model.gguf")


@override_settings(OLLAMA_BASE_URL="http://ollama:11434")
def test_copy_accepts_empty_success_response():
    session = Mock(spec=requests.Session)
    response = Mock()
    response.raise_for_status.return_value = None
    session.post.return_value = response

    _copy_model(session, "candidate", "qualified")

    session.post.assert_called_once()
    response.close.assert_called_once()


@override_settings(
    OLLAMA_BASE_URL="http://ollama:11434",
    MODEL_MAX_VRAM_BYTES=4_294_967_296,
)
@patch("llm.tasks._session")
def test_running_model_memory_reads_ollama_ps(mock_session):
    session = mock_session.return_value
    response = session.get.return_value
    response.json.return_value = {
        "models": [
            {
                "name": "qualified",
                "size": 3_000_000_000,
                "size_vram": 2_500_000_000,
            }
        ]
    }

    assert _running_model_memory("qualified") == {
        "size": 3_000_000_000,
        "size_vram": 2_500_000_000,
        "configured_max_vram": 4_294_967_296,
    }


@override_settings(OLLAMA_BASE_URL="http://ollama:11434")
@patch("llm.tasks._session")
def test_running_model_memory_fails_when_tag_missing(mock_session):
    mock_session.return_value.get.return_value.json.return_value = {"models": []}

    with pytest.raises(
        InstallationError,
        match="ollama_memory_probe_model_missing",
    ):
        _running_model_memory("missing")
