import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings

from llm.catalog import (
    CatalogValidationError,
    VerifiedCatalog,
    activate_configured_catalog,
    load_configured_catalog,
    verify_catalog,
)


class _LatestReleaseManager:
    def __init__(self, sequence: int) -> None:
        self._latest = SimpleNamespace(sequence=sequence)

    def select_for_update(self):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return self._latest


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


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda payload: payload["revoked_entry_ids"].append(
                payload["entries"][0]["id"]
            ),
            "catalog_entry_revoked_or_invalid",
        ),
        (
            lambda payload: payload["entries"].append(dict(payload["entries"][0])),
            "catalog_entry_duplicate",
        ),
        (
            lambda payload: payload["entries"][0].update(
                {"download_url": "https://example.com/owner/repo/model.gguf"}
            ),
            "catalog_entry_url_invalid",
        ),
        (
            lambda payload: payload["entries"][0].update(
                {"download_url": payload["entries"][0]["download_url"] + "?token=x"}
            ),
            "catalog_entry_url_invalid",
        ),
    ],
)
def test_catalog_rejects_revoked_duplicate_or_untrusted_urls(mutator, code):
    payload = json.loads(Path(settings.MODEL_CATALOG_FILE).read_text(encoding="utf-8"))
    signature = Path(settings.MODEL_CATALOG_SIGNATURE_FILE).read_text(encoding="ascii")
    mutator(payload)

    with pytest.raises(CatalogValidationError, match=code):
        verify_catalog(payload, signature)


@pytest.mark.parametrize(
    ("latest_sequence", "payload_sequence", "code"),
    [
        (7, 7, "catalog_replay"),
        (7, 6, "catalog_downgrade"),
    ],
)
def test_catalog_activation_rejects_replay_or_downgrade(
    monkeypatch,
    latest_sequence,
    payload_sequence,
    code,
):
    verified = load_configured_catalog()
    payload = dict(verified.payload)
    payload["sequence"] = payload_sequence
    monkeypatch.setattr(
        "llm.catalog.load_configured_catalog",
        lambda: VerifiedCatalog(
            payload=payload,
            canonical_bytes=verified.canonical_bytes,
            catalog_hash=verified.catalog_hash,
            issued_at=verified.issued_at,
            expires_at=verified.expires_at,
        ),
    )
    monkeypatch.setattr(
        "llm.catalog.ModelCatalogRelease.objects",
        _LatestReleaseManager(latest_sequence),
    )
    monkeypatch.setattr("llm.catalog.transaction.atomic", nullcontext)

    with pytest.raises(CatalogValidationError, match=code):
        activate_configured_catalog()
