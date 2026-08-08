"""Signed, replay-resistant local model catalog validation."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from llm.models import HardwareProfile, ModelCatalogRelease

CATALOG_SCHEMA_VERSION = 1
CATALOG_KEY_ID = "moksha-catalog-2026-01"
CATALOG_PUBLIC_KEY = "8-ZnT1w9jNC6DYkwhbqv6sszs4fwJ2Np3Nv32Fd9o14"
MAX_CATALOG_BYTES = 1_000_000
REQUIRED_ENTRY_FIELDS = {
    "architecture",
    "context_window",
    "download_url",
    "file",
    "id",
    "license",
    "ollama",
    "quantization",
    "repo",
    "revision",
    "sha256",
    "size",
}
CATALOG_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.gguf$")
CATALOG_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
CATALOG_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class CatalogValidationError(ValueError):
    """Stable catalog rejection with no untrusted detail."""

    @property
    def code(self) -> str:
        """Return a stable public catalog validation code."""
        value = self.args[0] if self.args else ""
        if isinstance(value, str) and re.fullmatch(r"[a-z0-9_]+", value):
            return value
        return "catalog_invalid"


@dataclass(frozen=True)
class VerifiedCatalog:
    payload: dict[str, Any]
    canonical_bytes: bytes
    catalog_hash: str
    issued_at: datetime
    expires_at: datetime


def _decode_urlsafe(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _parse_timestamp(value: object, code: str) -> datetime:
    if not isinstance(value, str):
        raise CatalogValidationError(code)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CatalogValidationError(code) from error
    if parsed.tzinfo is None:
        raise CatalogValidationError(code)
    return parsed.astimezone(UTC)


def _validate_entry(entry: object, revoked: set[str]) -> dict[str, Any]:
    if not isinstance(entry, dict) or set(entry) != REQUIRED_ENTRY_FIELDS:
        raise CatalogValidationError("catalog_entry_shape_invalid")
    entry_id = entry["id"]
    if not isinstance(entry_id, str) or not entry_id or entry_id in revoked:
        raise CatalogValidationError("catalog_entry_revoked_or_invalid")
    if (
        not isinstance(entry["sha256"], str)
        or len(entry["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in entry["sha256"])
    ):
        raise CatalogValidationError("catalog_entry_hash_invalid")
    if not isinstance(entry["size"], int) or entry["size"] <= 0:
        raise CatalogValidationError("catalog_entry_size_invalid")
    if not isinstance(entry["context_window"], int) or entry["context_window"] < 8192:
        raise CatalogValidationError("catalog_entry_context_invalid")
    if not all(
        isinstance(entry[field], str) and entry[field]
        for field in ("architecture", "license", "quantization")
    ):
        raise CatalogValidationError("catalog_entry_metadata_invalid")
    if not isinstance(entry["file"], str) or not CATALOG_FILE_RE.fullmatch(
        entry["file"]
    ):
        raise CatalogValidationError("catalog_entry_file_invalid")
    if not isinstance(entry["repo"], str) or not CATALOG_REPO_RE.fullmatch(
        entry["repo"]
    ):
        raise CatalogValidationError("catalog_entry_repo_invalid")
    if not isinstance(entry["revision"], str) or not CATALOG_REVISION_RE.fullmatch(
        entry["revision"]
    ):
        raise CatalogValidationError("catalog_entry_revision_invalid")
    parsed = urlparse(entry["download_url"])
    expected_path = f"/{entry['repo']}/resolve/{entry['revision']}/{entry['file']}"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "huggingface.co"
        or parsed.path != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise CatalogValidationError("catalog_entry_url_invalid")
    ollama = entry["ollama"]
    if (
        not isinstance(ollama, dict)
        or set(ollama) != {"num_ctx", "num_predict", "temperature", "template"}
        or not isinstance(ollama["num_ctx"], int)
        or ollama["num_ctx"] < 8192
        or not isinstance(ollama["num_predict"], int)
        or ollama["num_predict"] <= 0
        or not isinstance(ollama["temperature"], int | float)
        or not isinstance(ollama["template"], str)
    ):
        raise CatalogValidationError("catalog_entry_ollama_invalid")
    return entry


def verify_catalog(
    payload: object,
    signature_text: str,
    *,
    now: datetime | None = None,
) -> VerifiedCatalog:
    if not isinstance(payload, dict):
        raise CatalogValidationError("catalog_shape_invalid")
    required = {
        "entries",
        "expires_at",
        "issued_at",
        "key_id",
        "revoked_entry_ids",
        "schema_version",
        "sequence",
        "version",
    }
    if set(payload) != required:
        raise CatalogValidationError("catalog_shape_invalid")
    if payload["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise CatalogValidationError("catalog_schema_unsupported")
    if payload["key_id"] != CATALOG_KEY_ID:
        raise CatalogValidationError("catalog_key_unknown")
    if not isinstance(payload["sequence"], int) or payload["sequence"] <= 0:
        raise CatalogValidationError("catalog_sequence_invalid")
    if not isinstance(payload["version"], str) or not payload["version"]:
        raise CatalogValidationError("catalog_version_invalid")
    revoked_value = payload["revoked_entry_ids"]
    if not isinstance(revoked_value, list) or not all(
        isinstance(item, str) for item in revoked_value
    ):
        raise CatalogValidationError("catalog_revocations_invalid")
    revoked = set(revoked_value)
    entries_value = payload["entries"]
    if not isinstance(entries_value, list) or not entries_value:
        raise CatalogValidationError("catalog_entries_missing")
    entries = [_validate_entry(entry, revoked) for entry in entries_value]
    if len({entry["id"] for entry in entries}) != len(entries):
        raise CatalogValidationError("catalog_entry_duplicate")

    issued_at = _parse_timestamp(payload["issued_at"], "catalog_issued_at_invalid")
    expires_at = _parse_timestamp(payload["expires_at"], "catalog_expires_at_invalid")
    current = now or timezone.now()
    if issued_at > current or expires_at <= current or expires_at <= issued_at:
        raise CatalogValidationError("catalog_time_invalid")

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            _decode_urlsafe(CATALOG_PUBLIC_KEY)
        )
        public_key.verify(_decode_urlsafe(signature_text.strip()), canonical)
    except (InvalidSignature, ValueError, TypeError) as error:
        raise CatalogValidationError("catalog_signature_invalid") from error
    return VerifiedCatalog(
        payload=payload,
        canonical_bytes=canonical,
        catalog_hash=hashlib.sha256(canonical).hexdigest(),
        issued_at=issued_at,
        expires_at=expires_at,
    )


def load_configured_catalog() -> VerifiedCatalog:
    catalog_path = Path(settings.MODEL_CATALOG_FILE).resolve()
    signature_path = Path(settings.MODEL_CATALOG_SIGNATURE_FILE).resolve()
    if catalog_path.stat().st_size > MAX_CATALOG_BYTES:
        raise CatalogValidationError("catalog_too_large")
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        signature = signature_path.read_text(encoding="ascii")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CatalogValidationError("catalog_unreadable") from error
    return verify_catalog(payload, signature)


def activate_configured_catalog() -> ModelCatalogRelease:
    verified = load_configured_catalog()
    payload = verified.payload
    with transaction.atomic():
        latest = (
            ModelCatalogRelease.objects.select_for_update()
            .order_by("-sequence")
            .first()
        )
        if latest and payload["sequence"] <= latest.sequence:
            code = (
                "catalog_replay"
                if payload["sequence"] == latest.sequence
                else "catalog_downgrade"
            )
            raise CatalogValidationError(code)
        ModelCatalogRelease.objects.filter(active=True).update(active=False)
        release = ModelCatalogRelease.objects.create(
            schema_version=payload["schema_version"],
            sequence=payload["sequence"],
            version=payload["version"],
            key_id=payload["key_id"],
            catalog_hash=verified.catalog_hash,
            signature=Path(settings.MODEL_CATALOG_SIGNATURE_FILE)
            .read_text(encoding="ascii")
            .strip(),
            payload=payload,
            issued_at=verified.issued_at,
            expires_at=verified.expires_at,
            active=True,
        )
        HardwareProfile.objects.exclude(catalog_version=release.version).update(
            stale=True
        )
    return release
