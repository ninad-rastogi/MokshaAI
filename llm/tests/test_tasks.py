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
