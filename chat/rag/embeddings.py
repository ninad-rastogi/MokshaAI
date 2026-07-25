"""Native PostgreSQL pgvector store for Moksha AI."""

import logging
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from django.conf import settings
from pgvector.django import CosineDistance
from sentence_transformers import SentenceTransformer

from chat.models import DocumentChunk

logger = logging.getLogger("chat.rag.embeddings")


class PgVectorStore:
    """Vector store backed by PostgreSQL's HNSW cosine index."""

    def __init__(
        self,
        model_name: str = None,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(
                self.model_name,
                device=settings.EMBEDDING_DEVICE,
            )
            logger.info("Embedding model loaded successfully")
        return self._model

    def add_chunks(
        self,
        chunks: List[Dict],
        batch_size: int = 32,
        index_version: UUID = None,
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
            embeddings = self.model.encode(
                texts, show_progress_bar=False, normalize_embeddings=True
            )

            objects = [
                DocumentChunk(
                    scripture=chunk.get("scripture", ""),
                    file_name=chunk.get("file_name", ""),
                    page=chunk.get("page", 0),
                    chunk_text=chunk["text"],
                    chunk_type=chunk.get("chunk_type", ""),
                    language=chunk.get("language", ""),
                    index_version=index_version,
                    embedding=embedding.tolist(),
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
        scripture_filter: str = None,
        allowed_scriptures: Iterable[str] = None,
    ) -> List[Dict]:
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
        query_embedding = self.model.encode([query], normalize_embeddings=True)[
            0
        ].tolist()

        qs = DocumentChunk.objects.exclude(embedding__isnull=True)
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

    def get_scriptures(self) -> List[str]:
        """Return list of unique scripture names in the store."""
        return list(
            DocumentChunk.objects.values_list("scripture", flat=True).distinct()
        )
