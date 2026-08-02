import pytest

from chat.citations import (
    CitationValidationError,
    enforce_grounded_response,
    unsupported_citation_claims,
    validate_citations,
)


def test_validate_citations_normalizes_valid_record():
    result = validate_citations(
        [
            {
                "scripture": "Collection",
                "file_name": "volume.pdf",
                "page": 4,
                "score": 0.82,
                "excerpt": "A bounded source excerpt.",
            }
        ]
    )

    assert result[0]["page"] == 4
    assert result[0]["score"] == 0.82


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("scripture", "", "citation_scripture_invalid"),
        ("file_name", "", "citation_file_invalid"),
        ("page", 0, "citation_page_invalid"),
        ("score", 1.1, "citation_score_invalid"),
        ("excerpt", "", "citation_excerpt_invalid"),
    ],
)
def test_validate_citations_rejects_invalid_fields(field, value, code):
    source = {
        "scripture": "Collection",
        "file_name": "volume.pdf",
        "page": 4,
        "score": 0.82,
        "excerpt": "A bounded source excerpt.",
    }
    source[field] = value

    with pytest.raises(CitationValidationError, match=code):
        validate_citations([source])


def test_unsupported_citation_claims_detects_invented_source():
    sources = [
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "excerpt": "A bounded source excerpt.",
        }
    ]

    claims = unsupported_citation_claims(
        "The text says this. (From The Book of Life, File: Wisdom, Page 34)",
        sources,
    )

    assert claims == ["(From The Book of Life, File: Wisdom, Page 34)"]


def test_enforce_grounded_response_replaces_invented_source_claim():
    sources = [
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "excerpt": "Exact source passage.",
        }
    ]

    response = enforce_grounded_response(
        "Fake answer. (From The Book of Life, File: Wisdom, Page 34)",
        sources,
    )

    assert "The Book of Life" not in response
    assert "## Source verse" in response
    assert "Exact source passage." in response
