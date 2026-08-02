from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from chat.rag.embeddings import EmbeddingServiceError, PgVectorStore


@override_settings(
    EMBEDDING_MODEL="test-model",
    EMBEDDING_DIMENSIONS=3,
    EMBEDDING_SERVICE_URL="http://embedding:8010",
    EMBEDDING_SERVICE_TIMEOUT_SECONDS=5,
)
def test_embedding_client_validates_response_contract():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "model": "test-model",
        "embeddings": [[0.1, 0.2, 0.3]],
    }
    session = Mock()
    session.post.return_value = response

    with patch("chat.rag.embeddings.requests.Session", return_value=session):
        result = PgVectorStore()._embed(["hello"])

    assert result == [[0.1, 0.2, 0.3]]
    assert session.trust_env is False
    session.post.assert_called_once_with(
        "http://embedding:8010/embed",
        json={"texts": ["hello"]},
        timeout=5,
    )
    session.close.assert_called_once()


@override_settings(
    EMBEDDING_MODEL="test-model",
    EMBEDDING_DIMENSIONS=3,
    EMBEDDING_SERVICE_URL="http://embedding:8010",
    EMBEDDING_SERVICE_TIMEOUT_SECONDS=5,
)
def test_embedding_client_rejects_dimension_mismatch():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "model": "test-model",
        "embeddings": [[0.1, 0.2]],
    }
    session = Mock()
    session.post.return_value = response

    with (
        patch("chat.rag.embeddings.requests.Session", return_value=session),
        pytest.raises(EmbeddingServiceError, match="embedding_dimensions_invalid"),
    ):
        PgVectorStore()._embed(["hello"])
