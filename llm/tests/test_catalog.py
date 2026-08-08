import json
from pathlib import Path

import pytest
from django.conf import settings

from llm.catalog import CatalogValidationError, load_configured_catalog, verify_catalog


def test_bundled_catalog_signature_and_pins_are_valid():
    verified = load_configured_catalog()
    entry = verified.payload["entries"][0]

    assert entry["id"] == "qwen3-4b-instruct-2507-q3-k-m"
    assert entry["sha256"] == (
        "35295e9a0a42eff5ebc592412c754991c0b6cc36bf4f282b2a491b211476752d"
    )
    assert entry["size"] == 2_075_618_016
    assert entry["ollama"]["num_ctx"] == 8192


def test_catalog_rejects_modified_signed_payload():
    payload = json.loads(Path(settings.MODEL_CATALOG_FILE).read_text(encoding="utf-8"))
    signature = Path(settings.MODEL_CATALOG_SIGNATURE_FILE).read_text(encoding="ascii")
    payload["entries"][0]["size"] += 1

    with pytest.raises(CatalogValidationError, match="catalog_signature_invalid"):
        verify_catalog(payload, signature)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("file", "../escape.gguf", "catalog_entry_file_invalid"),
        ("file", "nested/model.gguf", "catalog_entry_file_invalid"),
        ("file", "model.bin", "catalog_entry_file_invalid"),
        ("repo", "owner/repo/extra", "catalog_entry_repo_invalid"),
        ("revision", "main", "catalog_entry_revision_invalid"),
    ],
)
def test_catalog_rejects_unpinned_or_unsafe_entry_paths(field, value, code):
    payload = json.loads(Path(settings.MODEL_CATALOG_FILE).read_text(encoding="utf-8"))
    signature = Path(settings.MODEL_CATALOG_SIGNATURE_FILE).read_text(encoding="ascii")
    payload["entries"][0][field] = value

    with pytest.raises(CatalogValidationError, match=code):
        verify_catalog(payload, signature)
