"""Security helpers for BYOK storage and custom model endpoints."""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError


class KeyUnavailable(ImproperlyConfigured):
    """Raised when BYOK encryption is requested without a valid master key."""


class DecryptionFailed(ValueError):
    """Raised when encrypted BYOK material fails authentication."""


@dataclass(frozen=True)
class EndpointValidationResult:
    """Validated public endpoint details."""

    normalized_url: str
    resolved_ips: tuple[str, ...]


def _decode_key(raw: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(raw)
    except Exception as exc:
        raise KeyUnavailable("byok_master_key_invalid") from exc
    if len(key) != 32:
        raise KeyUnavailable("byok_master_key_invalid_length")
    return key


def active_key_version() -> int:
    keyring_file = getattr(settings, "BYOK_KEYRING_FILE", "") or ""
    if not keyring_file:
        return int(getattr(settings, "BYOK_ACTIVE_KEY_VERSION", 1))
    try:
        payload = json.loads(Path(keyring_file).read_text(encoding="utf-8"))
        version = int(payload["active_version"])
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise KeyUnavailable("byok_keyring_invalid") from exc
    if version <= 0:
        raise KeyUnavailable("byok_keyring_invalid")
    return version


def _load_master_key(version: int | None = None) -> bytes:
    selected_version = version or active_key_version()
    keyring_file = getattr(settings, "BYOK_KEYRING_FILE", "") or ""
    if keyring_file:
        try:
            payload = json.loads(Path(keyring_file).read_text(encoding="utf-8"))
            keys = payload["keys"]
            raw = keys[str(selected_version)]
        except (
            KeyError,
            OSError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise KeyUnavailable("byok_master_key_unavailable") from exc
        if not isinstance(raw, str):
            raise KeyUnavailable("byok_master_key_invalid")
        return _decode_key(raw)

    if selected_version != int(getattr(settings, "BYOK_ACTIVE_KEY_VERSION", 1)):
        raise KeyUnavailable("byok_master_key_version_unavailable")
    raw = getattr(settings, "BYOK_MASTER_KEY", "") or ""
    key_file = getattr(settings, "BYOK_MASTER_KEY_FILE", "") or ""
    if key_file:
        try:
            raw = Path(key_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise KeyUnavailable("byok_master_key_unavailable") from exc
    if not raw:
        raise KeyUnavailable("byok_master_key_unavailable")
    return _decode_key(raw)


def aad_for_connection(user_id: int, connection_id: str, key_version: int) -> bytes:
    """Bind ciphertext to one user, connection, and key version."""

    return (
        f"moksha-byok:v{key_version}:user:{user_id}:connection:{connection_id}".encode()
    )


def encrypt_secret(
    secret: str,
    aad: bytes,
    *,
    key_version: int | None = None,
) -> tuple[str, str]:
    """Encrypt a secret with AES-256-GCM and return nonce/ciphertext."""

    key = _load_master_key(key_version)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, secret.encode("utf-8"), aad)
    return (
        base64.urlsafe_b64encode(nonce).decode("ascii"),
        base64.urlsafe_b64encode(ciphertext).decode("ascii"),
    )


def decrypt_secret(
    nonce: str,
    ciphertext: str,
    aad: bytes,
    *,
    key_version: int | None = None,
) -> str:
    """Decrypt a secret, failing closed on missing keys or AAD/tag mismatch."""

    key = _load_master_key(key_version)
    try:
        plaintext = AESGCM(key).decrypt(
            base64.urlsafe_b64decode(nonce),
            base64.urlsafe_b64decode(ciphertext),
            aad,
        )
    except (InvalidTag, ValueError) as exc:
        raise DecryptionFailed("byok_decryption_failed") from exc
    return plaintext.decode("utf-8")


def _resolve_host(host: str) -> tuple[str, ...]:
    addresses = {
        str(result[4][0])
        for result in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    }
    return tuple(sorted(addresses))


def _ip_is_forbidden(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(
        [
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ]
    )


def validate_public_https_endpoint(
    url: str,
    *,
    allow_private: bool = False,
    resolved_ips: Iterable[str] | None = None,
) -> EndpointValidationResult:
    """Validate a custom provider endpoint against SSRF guardrails."""

    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise ValidationError("endpoint_must_use_public_https")
    if not parsed.hostname:
        raise ValidationError("endpoint_host_required")
    if parsed.username or parsed.password:
        raise ValidationError("endpoint_credentials_forbidden")
    if parsed.port and parsed.port not in {443, 8443}:
        raise ValidationError("endpoint_port_forbidden")

    pins = (
        tuple(resolved_ips)
        if resolved_ips is not None
        else _resolve_host(parsed.hostname)
    )
    if not pins:
        raise ValidationError("endpoint_dns_required")
    if not allow_private and any(_ip_is_forbidden(address) for address in pins):
        raise ValidationError("endpoint_private_network_forbidden")

    normalized = parsed._replace(fragment="", query="").geturl().rstrip("/")
    return EndpointValidationResult(normalized_url=normalized, resolved_ips=pins)


def rewrap_byok_connections(target_version: int) -> int:
    """Atomically re-encrypt every stored BYOK secret with one key version."""

    if target_version <= 0:
        raise KeyUnavailable("byok_target_version_invalid")
    _load_master_key(target_version)

    from django.db import transaction

    from llm.models import ModelConnection

    updated = 0
    with transaction.atomic():
        connections = ModelConnection.objects.select_for_update().exclude(
            encrypted_api_key="",
        )
        for connection in connections:
            if not connection.user_id:
                raise DecryptionFailed("byok_owner_missing")
            old_aad = aad_for_connection(
                connection.user_id,
                str(connection.pk),
                connection.key_version,
            )
            plaintext = decrypt_secret(
                connection.api_key_nonce,
                connection.encrypted_api_key,
                old_aad,
                key_version=connection.key_version,
            )
            new_aad = aad_for_connection(
                connection.user_id,
                str(connection.pk),
                target_version,
            )
            nonce, ciphertext = encrypt_secret(
                plaintext,
                new_aad,
                key_version=target_version,
            )
            connection.api_key_nonce = nonce
            connection.encrypted_api_key = ciphertext
            connection.key_version = target_version
            connection.save(
                update_fields=[
                    "api_key_nonce",
                    "encrypted_api_key",
                    "key_version",
                    "updated_at",
                ]
            )
            updated += 1
    return updated
