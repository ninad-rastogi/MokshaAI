"""Provider-neutral probing with SSRF-safe request handling."""

from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass
from http.client import HTTPSConnection
from typing import Any
from urllib.parse import urljoin, urlparse

from django.core.exceptions import ValidationError
from django.utils import timezone

from llm.models import ModelConnection
from llm.security import validate_public_https_endpoint

MAX_PROBE_BODY_BYTES = 256_000
PROBE_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class ProbeResult:
    """Sanitized provider probe result."""

    status: str
    detail: str
    models: tuple[str, ...] = ()


class NoRedirectHTTPSConnection(HTTPSConnection):
    """HTTPSConnection wrapper that disables proxy-env inheritance by design."""


def _sanitize_detail(value: str) -> str:
    clean = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return clean[:240]


def _classify_http_status(status: int) -> str:
    if status in {401, 403}:
        return ModelConnection.Status.AUTH_INVALID
    if status == 404:
        return ModelConnection.Status.MODEL_UNAVAILABLE
    if status == 429:
        return ModelConnection.Status.RATE_LIMITED
    if 500 <= status <= 599:
        return ModelConnection.Status.DEGRADED
    return ModelConnection.Status.UNREACHABLE


def _json_get(url: str, api_key: str = "") -> tuple[int, dict[str, Any]]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise ValidationError("probe_endpoint_invalid")
    if parsed.port and parsed.port not in {443, 8443}:
        raise ValidationError("probe_port_forbidden")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    context = ssl.create_default_context()
    connection = NoRedirectHTTPSConnection(
        parsed.hostname,
        parsed.port or 443,
        timeout=PROBE_TIMEOUT_SECONDS,
        context=context,
    )
    headers = {"Accept": "application/json", "User-Agent": "MokshaAI/2"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_PROBE_BODY_BYTES + 1)
    finally:
        connection.close()
    if len(raw) > MAX_PROBE_BODY_BYTES:
        raise ValidationError("probe_body_too_large")
    payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
    if not isinstance(payload, dict):
        raise ValidationError("probe_response_invalid")
    return response.status, payload


def _extract_openai_models(payload: dict[str, Any]) -> tuple[str, ...]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        return ()
    models = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return tuple(sorted(set(models)))


def _extract_ollama_models(payload: dict[str, Any]) -> tuple[str, ...]:
    data = payload.get("models", [])
    if not isinstance(data, list):
        return ()
    models = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            models.append(item["name"])
    return tuple(sorted(set(models)))


def probe_connection(connection: ModelConnection) -> ProbeResult:
    """Probe one connection, returning only sanitized status details."""

    if connection.dialect == ModelConnection.Dialect.BUILTIN_OLLAMA:
        return ProbeResult(
            status=ModelConnection.Status.CONNECTED,
            detail="Built-in Ollama is managed by the local runtime.",
        )

    try:
        validation = validate_public_https_endpoint(
            connection.endpoint_url,
            allow_private=connection.is_admin_connection,
            resolved_ips=connection.dns_pins or None,
        )
    except ValidationError:
        return ProbeResult(
            status=ModelConnection.Status.ENDPOINT_INVALID,
            detail="Endpoint did not pass safety validation.",
        )

    try:
        api_key = connection.get_api_key()
    except Exception:
        return ProbeResult(
            status=ModelConnection.Status.AUTH_INVALID,
            detail="Stored credential could not be decrypted.",
        )

    if connection.dialect == ModelConnection.Dialect.OPENAI_COMPATIBLE:
        url = urljoin(f"{validation.normalized_url}/", "models")
        extractor = _extract_openai_models
    elif connection.dialect == ModelConnection.Dialect.OLLAMA_COMPATIBLE:
        url = urljoin(f"{validation.normalized_url}/", "api/tags")
        extractor = _extract_ollama_models
    else:
        return ProbeResult(
            status=ModelConnection.Status.ENDPOINT_INVALID,
            detail="Unsupported provider dialect.",
        )

    try:
        status, payload = _json_get(url, api_key)
    except OSError, socket.timeout, ssl.SSLError, json.JSONDecodeError, ValidationError:
        return ProbeResult(
            status=ModelConnection.Status.UNREACHABLE,
            detail="Provider probe failed without exposing remote error details.",
        )
    if status < 200 or status >= 300:
        return ProbeResult(
            status=_classify_http_status(status),
            detail=_sanitize_detail(f"Provider returned HTTP {status}."),
        )

    models = extractor(payload)
    if not models:
        return ProbeResult(
            status=ModelConnection.Status.MODEL_UNAVAILABLE,
            detail="Provider did not report any usable models.",
        )
    return ProbeResult(
        status=ModelConnection.Status.CONNECTED,
        detail="Provider probe succeeded.",
        models=models,
    )


def update_connection_probe(connection: ModelConnection) -> ProbeResult:
    """Probe and persist connection status."""

    result = probe_connection(connection)
    connection.status = result.status
    connection.sanitized_detail = result.detail
    connection.last_checked_at = timezone.now()
    connection.save(
        update_fields=["status", "sanitized_detail", "last_checked_at", "updated_at"]
    )
    return result
