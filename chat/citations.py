"""Typed, bounded citation validation shared by generation paths."""

from __future__ import annotations

import math
import re
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


_BRACKET_CITATION_RE = re.compile(
    r"\[(?P<scripture>[^\],]{1,200}),\s*(?P<file>[^\],]{1,500}),\s*p\.\s*(?P<page>\d+)\]",
    re.IGNORECASE,
)
_PAREN_CITATION_RE = re.compile(
    r"\((?:From\s+)?(?P<scripture>[^,()]{1,200}),\s*File:\s*(?P<file>[^,()]{1,500}),\s*Page\s*(?P<page>\d+)\)",
    re.IGNORECASE,
)
_SOURCE_LIKE_RE = re.compile(
    r"\b(?:File:\s*[^,\n)]+|Page\s+\d+|From\s+(?:The\s+)?[A-Z][A-Za-z0-9 ':-]{2,80})",
)


def _norm(value: object) -> str:
    return str(value).strip().casefold()


def _source_key(source: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _norm(source.get("scripture", "")),
        _norm(source.get("file_name", "")),
        _norm(source.get("page", "")),
    )


def unsupported_citation_claims(
    text: str,
    sources: list[dict[str, Any]],
) -> list[str]:
    """Return citation-like claims not backed by retrieved source metadata."""
    allowed = {_source_key(source) for source in sources}
    unsupported: list[str] = []
    for pattern in (_BRACKET_CITATION_RE, _PAREN_CITATION_RE):
        for match in pattern.finditer(text):
            key = (
                _norm(match.group("scripture")),
                _norm(match.group("file")),
                _norm(match.group("page")),
            )
            if key not in allowed:
                unsupported.append(match.group(0))

    if not sources:
        unsupported.extend(match.group(0) for match in _SOURCE_LIKE_RE.finditer(text))
    return unsupported


def enforce_grounded_response(
    text: str,
    sources: list[dict[str, Any]],
) -> str:
    """Fail closed against invented source names, files, and pages."""
    if not unsupported_citation_claims(text, sources):
        return text
    if not sources:
        return (
            "I cannot quote or cite a scripture for this answer because no "
            "indexed source evidence was used. I can still offer general "
            "spiritual guidance, but it should not be treated as a cited text."
        )

    source = sources[0]
    excerpt = str(source.get("excerpt", "")).strip()
    scripture = str(source.get("scripture", "Indexed source")).strip()
    file_name = str(source.get("file_name", "source")).strip()
    page = source.get("page", "N/A")
    return (
        "## Source verse\n"
        f"> {excerpt}\n\n"
        "## Meaning\n"
        f"This is the exact retrieved passage from [{scripture}, {file_name}, "
        f"p. {page}]. I cannot verify any other book, file, page, or verse for "
        "this answer.\n\n"
        "## Guidance\n"
        "Stay with what the retrieved passage directly supports. Pause, observe "
        "the pull inside you, and choose the clearest next action without adding "
        "an invented book, page, or verse."
    )


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
