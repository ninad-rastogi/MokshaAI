"""Security helpers for BYOK storage and custom model endpoints."""

from __future__ import annotations

import base64
import ipaddress
import os
import socket
from dataclasses import dataclass
from typing import Iterable
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


def _load_master_key() -> bytes:
    raw = getattr(settings, "BYOK_MASTER_KEY", "") or ""
    key_file = getattr(settings, "BYOK_MASTER_KEY_FILE", "") or ""
    if key_file:
        try:
            raw = open(key_file, encoding="utf-8").read().strip()
        except OSError as exc:
            raise KeyUnavailable("byok_master_key_unavailable") from exc
    if not raw:
        raise KeyUnavailable("byok_master_key_unavailable")
    try:
        key = base64.urlsafe_b64decode(raw)
    except Exception as exc:
        raise KeyUnavailable("byok_master_key_invalid") from exc
    if len(key) != 32:
        raise KeyUnavailable("byok_master_key_invalid_length")
    return key


def aad_for_connection(user_id: int, connection_id: str, key_version: int) -> bytes:
    """Bind ciphertext to one user, connection, and key version."""

    return (
        f"moksha-byok:v{key_version}:user:{user_id}:connection:{connection_id}".encode(
            "utf-8"
        )
    )


def encrypt_secret(secret: str, aad: bytes) -> tuple[str, str]:
    """Encrypt a secret with AES-256-GCM and return nonce/ciphertext."""

    key = _load_master_key()
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, secret.encode("utf-8"), aad)
    return (
        base64.urlsafe_b64encode(nonce).decode("ascii"),
        base64.urlsafe_b64encode(ciphertext).decode("ascii"),
    )


def decrypt_secret(nonce: str, ciphertext: str, aad: bytes) -> str:
    """Decrypt a secret, failing closed on missing keys or AAD/tag mismatch."""

    key = _load_master_key()
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
