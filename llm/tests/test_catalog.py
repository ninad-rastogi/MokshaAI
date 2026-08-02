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
