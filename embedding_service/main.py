"""Private embedding sidecar for Moksha AI."""

import os
from functools import lru_cache
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

app = FastAPI(title="Moksha Embedding Service", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: List[str] = Field(min_length=1, max_length=64)


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
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
