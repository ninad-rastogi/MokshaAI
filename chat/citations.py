"""Typed, bounded citation validation shared by generation paths."""

from __future__ import annotations

import math
from typing import Any, TypedDict

MAX_CITATIONS = 8


class Citation(TypedDict):
    scripture: str
    file_name: str
    page: int
    score: float
    excerpt: str


class CitationValidationError(ValueError):
    """Raised when model/retrieval citation data is unsafe to persist."""


def validate_citations(raw_sources: list[dict[str, Any]]) -> list[Citation]:
    if len(raw_sources) > MAX_CITATIONS:
        raise CitationValidationError("too_many_citations")

    citations: list[Citation] = []
    for raw in raw_sources:
        scripture = raw.get("scripture")
        file_name = raw.get("file_name")
        page = raw.get("page")
        score = raw.get("score")
        excerpt = raw.get("excerpt")
        if not isinstance(scripture, str) or not 1 <= len(scripture) <= 200:
            raise CitationValidationError("citation_scripture_invalid")
        if not isinstance(file_name, str) or not 1 <= len(file_name) <= 500:
            raise CitationValidationError("citation_file_invalid")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise CitationValidationError("citation_page_invalid")
        if (
            isinstance(score, bool)
            or not isinstance(score, int | float)
            or not math.isfinite(float(score))
            or not 0 <= float(score) <= 1
        ):
            raise CitationValidationError("citation_score_invalid")
        if not isinstance(excerpt, str) or not 1 <= len(excerpt) <= 600:
            raise CitationValidationError("citation_excerpt_invalid")
        citations.append(
            {
                "scripture": scripture,
                "file_name": file_name,
                "page": page,
                "score": float(score),
                "excerpt": excerpt,
            }
        )
    return citations
