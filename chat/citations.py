"""Typed, bounded citation validation shared by generation paths."""

from __future__ import annotations

import math
import re
from typing import Any, NotRequired, TypedDict

MAX_CITATIONS = 8
MAX_EXCERPT_CHARS = 600
MAX_SOURCE_TEXT_CHARS = 2000
MAX_VERSE_CHARS = 1200
MAX_TRANSLATION_CHARS = 1600


class Citation(TypedDict):
    scripture: str
    file_name: str
    page: int
    score: float
    excerpt: str
    source_text: NotRequired[str]
    verse_text: NotRequired[str]
    sanskrit_text: NotRequired[str]
    translation: NotRequired[str]


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
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def _norm(value: object) -> str:
    return str(value).strip().casefold()


def _source_key(source: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _norm(source.get("scripture", "")),
        _norm(source.get("file_name", "")),
        _norm(source.get("page", "")),
    )


def _clip_text(value: str, limit: int) -> str:
    text = " ".join(value.split()) if limit <= MAX_EXCERPT_CHARS else value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _citation_text_parts(text: str) -> dict[str, str]:
    lines = _clean_lines(text)
    devanagari_lines = [line for line in lines if _DEVANAGARI_RE.search(line)]
    parts: dict[str, str] = {
        "source_text": _clip_text(text, MAX_SOURCE_TEXT_CHARS),
    }
    if devanagari_lines:
        sanskrit = "\n".join(devanagari_lines[:8])
        parts["sanskrit_text"] = _clip_text(sanskrit, MAX_VERSE_CHARS)
        parts["verse_text"] = parts["sanskrit_text"]
        translation_lines = [line for line in lines if line not in devanagari_lines]
        if translation_lines:
            parts["translation"] = _clip_text(
                "\n".join(translation_lines),
                MAX_TRANSLATION_CHARS,
            )
    else:
        first_block = text.strip().split("\n\n", 1)[0].strip()
        parts["verse_text"] = _clip_text(first_block or text, MAX_VERSE_CHARS)
    return parts


def citation_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Build public citation metadata from one retrieved chunk."""
    text = str(chunk.get("text", "")).strip()
    page = chunk.get("page", 1)
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        page = 1
    citation = {
        "scripture": str(chunk.get("scripture", "Unknown")).strip() or "Unknown",
        "page": page,
        "file_name": str(chunk.get("file_name", "Unknown")).strip() or "Unknown",
        "score": float(chunk.get("score", 0.0) or 0.0),
        "excerpt": _clip_text(text, MAX_EXCERPT_CHARS),
    }
    citation.update(_citation_text_parts(text))
    return citation


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
        citation: Citation = {
            "scripture": scripture,
            "file_name": file_name,
            "page": page,
            "score": float(score),
            "excerpt": excerpt,
        }
        source_text = raw.get("source_text")
        if source_text is not None:
            if (
                not isinstance(source_text, str)
                or not 1 <= len(source_text) <= MAX_SOURCE_TEXT_CHARS
            ):
                raise CitationValidationError("citation_source_text_invalid")
            citation["source_text"] = source_text
        verse_text = raw.get("verse_text")
        if verse_text is not None:
            if (
                not isinstance(verse_text, str)
                or not 1 <= len(verse_text) <= MAX_VERSE_CHARS
            ):
                raise CitationValidationError("citation_verse_text_invalid")
            citation["verse_text"] = verse_text
        sanskrit_text = raw.get("sanskrit_text")
        if sanskrit_text is not None:
            if (
                not isinstance(sanskrit_text, str)
                or not 1 <= len(sanskrit_text) <= MAX_VERSE_CHARS
            ):
                raise CitationValidationError("citation_sanskrit_text_invalid")
            citation["sanskrit_text"] = sanskrit_text
        translation = raw.get("translation")
        if translation is not None:
            if (
                not isinstance(translation, str)
                or not 1 <= len(translation) <= MAX_TRANSLATION_CHARS
            ):
                raise CitationValidationError("citation_translation_invalid")
            citation["translation"] = translation
        citations.append(citation)
    return citations
