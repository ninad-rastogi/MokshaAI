import pytest

from chat.citations import (
    CitationValidationError,
    citation_from_chunk,
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


def test_citation_from_chunk_extracts_sanskrit_and_translation():
    citation = citation_from_chunk(
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "chunk_type": "shloka",
            "text": (
                "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन\n"
                "You have a right to action, not to its fruits."
            ),
        }
    )

    assert citation["sanskrit_text"] == "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन"
    assert citation["verse_text"] == "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन"
    assert citation["translation"] == "You have a right to action, not to its fruits."
    assert citation["source_text"].startswith("कर्मण्येवाधिकारस्ते")


def test_citation_from_chunk_does_not_present_hindi_prose_as_sanskrit():
    citation = citation_from_chunk(
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 5,
            "score": 0.82,
            "chunk_type": "translation",
            "text": "मन को शांत रखने के लिए नियमित अभ्यास आवश्यक है।",
        }
    )

    assert "verse_text" not in citation
    assert "sanskrit_text" not in citation
    assert citation["source_text"].startswith("मन को शांत")


def test_citation_from_chunk_extracts_labelled_verse_and_translation():
    citation = citation_from_chunk(
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "text": (
                "Sanskrit verse:\n" "सत्यं वद।\n\n" "Translation:\n" "Speak truth."
            ),
        }
    )

    assert citation["sanskrit_text"] == "सत्यं वद।"
    assert citation["verse_text"] == "सत्यं वद।"
    assert citation["translation"] == "Speak truth."


def test_citation_from_chunk_prefers_explicit_metadata():
    citation = citation_from_chunk(
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "text": "Loose retrieved passage.",
            "metadata": {
                "sanskrit_text": "अहिंसा परमो धर्मः",
                "translation": "Non-harm is a highest duty.",
            },
        }
    )

    assert citation["sanskrit_text"] == "अहिंसा परमो धर्मः"
    assert citation["verse_text"] == "अहिंसा परमो धर्मः"
    assert citation["translation"] == "Non-harm is a highest duty."


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


def test_validate_citations_keeps_structured_optional_fields():
    result = validate_citations(
        [
            {
                "scripture": "Collection",
                "file_name": "volume.pdf",
                "page": 4,
                "score": 0.82,
                "excerpt": "A bounded source excerpt.",
                "source_text": "Full retrieved passage.",
                "verse_text": "Exact verse.",
                "sanskrit_text": "कर्मण्येवाधिकारस्ते",
                "translation": "Translation.",
            }
        ]
    )

    assert result[0]["source_text"] == "Full retrieved passage."
    assert result[0]["sanskrit_text"] == "कर्मण्येवाधिकारस्ते"


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


def test_unsupported_citation_claims_detects_source_colon_book_claim():
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
        (
            'The sacred text says, "He who is mindful will find peace." '
            "(Source: The Book of Life, File: Wisdom for the Way, Page 34)"
        ),
        sources,
    )

    assert claims == ["(Source: The Book of Life, File: Wisdom for the Way, Page 34)"]


def test_unsupported_citation_claims_allows_source_colon_for_retrieved_source():
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
        "Source: Collection, volume.pdf, p. 4",
        sources,
    )

    assert claims == []


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


def test_enforce_grounded_response_replaces_source_colon_invented_book():
    sources = [
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "excerpt": "Exact source passage.",
            "sanskrit_text": "योगस्थः कुरु कर्माणि।",
            "translation": "Established in steadiness, perform action.",
        }
    ]

    response = enforce_grounded_response(
        (
            'The sacred text says, "He who is mindful will find peace." '
            "(Source: The Book of Life, File: Wisdom for the Way, Page 34)"
        ),
        sources,
    )

    assert "The Book of Life" not in response
    assert "> योगस्थः कुरु कर्माणि।" in response
    assert "Established in steadiness, perform action." in response


def test_enforce_grounded_response_uses_structured_verse_and_translation():
    sources = [
        {
            "scripture": "Collection",
            "file_name": "volume.pdf",
            "page": 4,
            "score": 0.82,
            "excerpt": "Fallback excerpt.",
            "sanskrit_text": "सत्यं वद।",
            "translation": "Speak truth.",
        }
    ]

    response = enforce_grounded_response(
        "Fake answer. (From The Book of Life, File: Wisdom, Page 34)",
        sources,
    )

    assert "> सत्यं वद।" in response
    assert "Speak truth." in response
    assert "Fallback excerpt." not in response
