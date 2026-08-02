"""PgVector storage backed by the private embedding sidecar."""

import logging
from collections.abc import Iterable
from typing import Any
from uuid import UUID

import requests
from django.conf import settings
from pgvector.django import CosineDistance

from chat.models import DocumentChunk

logger = logging.getLogger("chat.rag.embeddings")

MAX_EMBED_TEXTS = 64
MAX_EMBED_TEXT_CHARS = 12_000


class EmbeddingServiceError(RuntimeError):
    """Raised when the private embedding service violates its contract."""


class PgVectorStore:
    """Vector store backed by PostgreSQL's HNSW cosine index."""

    def __init__(
        self,
        model_name: str | None = None,
        service_url: str | None = None,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.service_url = (service_url or settings.EMBEDDING_SERVICE_URL).rstrip("/")

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or len(texts) > MAX_EMBED_TEXTS:
            raise EmbeddingServiceError("embedding_batch_invalid")
        if any(not text or len(text) > MAX_EMBED_TEXT_CHARS for text in texts):
            raise EmbeddingServiceError("embedding_text_invalid")

        session = requests.Session()
        session.trust_env = False
        try:
            response = session.post(
                f"{self.service_url}/embed",
                json={"texts": texts},
                timeout=settings.EMBEDDING_SERVICE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except (
            requests.RequestException,
            requests.JSONDecodeError,
            ValueError,
        ) as error:
            raise EmbeddingServiceError("embedding_service_unavailable") from error
        finally:
            session.close()

        if (
            not isinstance(payload, dict)
            or payload.get("model") != self.model_name
            or not isinstance(payload.get("embeddings"), list)
            or len(payload["embeddings"]) != len(texts)
        ):
            raise EmbeddingServiceError("embedding_response_invalid")

        embeddings: list[list[float]] = []
        for embedding in payload["embeddings"]:
            if (
                not isinstance(embedding, list)
                or len(embedding) != settings.EMBEDDING_DIMENSIONS
                or any(not isinstance(value, int | float) for value in embedding)
            ):
                raise EmbeddingServiceError("embedding_dimensions_invalid")
            embeddings.append([float(value) for value in embedding])
        return embeddings

    def add_chunks(
        self,
        chunks: list[dict],
        batch_size: int = 32,
        index_version: UUID | None = None,
    ) -> int:
        """
        Add document chunks to the vector store.

        Args:
            chunks: List of dicts with keys:
                scripture, file_name, page, text,
                chunk_type, language
            batch_size: Number of chunks to embed at once

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        total_added = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = self._embed(texts)

            objects = [
                DocumentChunk(
                    scripture=chunk.get("scripture", ""),
                    file_name=chunk.get("file_name", ""),
                    page=chunk.get("page", 0),
                    chunk_text=chunk["text"],
                    chunk_type=chunk.get("chunk_type", ""),
                    language=chunk.get("language", ""),
                    index_version=index_version,
                    embedding=embedding,
                )
                for chunk, embedding in zip(batch, embeddings)
            ]

            DocumentChunk.objects.bulk_create(objects, batch_size=batch_size)
            total_added += len(objects)

        logger.info(f"Added {total_added} chunks to document_chunks")
        return total_added

    def search(
        self,
        query: str,
        top_k: int = 3,
        scripture_filter: str | None = None,
        allowed_scriptures: Iterable[str] | None = None,
        index_versions: Iterable[UUID] | None = None,
    ) -> list[dict]:
        """
        Search using PostgreSQL's native cosine-distance operator.

        Args:
            query: The search query text
            top_k: Number of results to return
            scripture_filter: Optional scripture name to filter by

        Returns:
            List of dicts with keys: text, scripture, file_name,
            page, chunk_type, language, score
        """
        query_embedding = self._embed([query])[0]

        qs = DocumentChunk.objects.exclude(embedding__isnull=True)
        if index_versions is None:
            from scriptures.models import Scripture

            active_versions = Scripture.objects.exclude(
                active_index_version__isnull=True
            ).values_list("active_index_version_id", flat=True)
            qs = qs.filter(index_version__in=active_versions)
        else:
            qs = qs.filter(index_version__in=list(index_versions))
        if scripture_filter:
            qs = qs.filter(scripture=scripture_filter)
        if allowed_scriptures is not None:
            qs = qs.filter(scripture__in=list(allowed_scriptures))

        rows = qs.annotate(
            distance=CosineDistance("embedding", query_embedding)
        ).order_by("distance")[:top_k]
        return [
            {
                "text": row.chunk_text,
                "scripture": row.scripture,
                "file_name": row.file_name,
                "page": row.page,
                "chunk_type": row.chunk_type,
                "language": row.language,
                "score": round(1 - float(row.distance), 4),
            }
            for row in rows
        ]

    def clear_scripture(self, scripture_name: str) -> int:
        """Remove all chunks for a given scripture."""
        count, _ = DocumentChunk.objects.filter(scripture=scripture_name).delete()
        logger.info(f"Cleared {count} chunks for {scripture_name}")
        return count

    def count(self) -> int:
        """Return total number of chunks in the store."""
        return DocumentChunk.objects.count()

    def get_scriptures(self) -> list[str]:
        """Return list of unique scripture names in the store."""
        return list(
            DocumentChunk.objects.values_list("scripture", flat=True).distinct()
        )
