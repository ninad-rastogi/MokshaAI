"""Private embedding sidecar for Moksha AI."""

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sentence_transformers import SentenceTransformer

app = FastAPI(title="Moksha Embedding Service", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, texts: list[str]) -> list[str]:
        if any(not text or len(text) > 12_000 for text in texts):
            raise ValueError("Each text must contain 1 to 12000 characters.")
        return texts


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str


@lru_cache(maxsize=1)
def model() -> SentenceTransformer:
    return SentenceTransformer(
        os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        device=os.getenv("EMBEDDING_DEVICE", "cpu"),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        loaded = model()
    except (OSError, RuntimeError) as error:
        raise HTTPException(
            status_code=503,
            detail="embedding_model_unavailable",
        ) from error
    dimensions = loaded.get_sentence_embedding_dimension()
    if dimensions != int(os.getenv("EMBEDDING_DIMENSIONS", "1024")):
        raise HTTPException(
            status_code=503,
            detail="embedding_dimensions_mismatch",
        )
    return {
        "status": "ready",
        "model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
    }


@app.post("/embed")
def embed(request: EmbedRequest) -> EmbedResponse:
    embeddings = model().encode(
        request.texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return EmbedResponse(
        embeddings=[embedding.tolist() for embedding in embeddings],
        model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
    )
