from unittest.mock import Mock, call, patch

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


def test_add_chunks_reports_committed_batch_progress():
    chunks = [
        {
            "scripture": "Test collection",
            "file_name": "volume.pdf",
            "page": index + 1,
            "text": f"passage {index}",
        }
        for index in range(5)
    ]
    progress = Mock()

    with (
        patch.object(
            PgVectorStore,
            "_embed",
            side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
        ),
        patch("chat.rag.embeddings.DocumentChunk.objects.bulk_create"),
    ):
        added = PgVectorStore().add_chunks(
            chunks,
            batch_size=2,
            progress_callback=progress,
        )

    assert added == 5
    assert progress.call_args_list == [call(2, 5), call(4, 5), call(5, 5)]
