"""Provider-neutral probing with SSRF-safe request handling."""

from __future__ import annotations

import json
import ssl
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
from typing import Any
from urllib.parse import urljoin, urlparse

from django.core.exceptions import ValidationError
from django.utils import timezone

from llm.models import ModelConnection
from llm.security import (
    DecryptionFailed,
    KeyUnavailable,
    validate_public_https_endpoint,
)

MAX_PROBE_BODY_BYTES = 256_000
MAX_COMPLETION_BODY_BYTES = 1_000_000
PROBE_TIMEOUT_SECONDS = 8
COMPLETION_TIMEOUT_SECONDS = 90


@dataclass(frozen=True)
class ProbeResult:
    """Sanitized provider probe result."""

    status: str
    detail: str
    models: tuple[str, ...] = ()


class ProviderResponseError(RuntimeError):
    """Raised when a provider returns a structurally invalid response."""


class ProviderRequestFailed(RuntimeError):
    """Raised for provider HTTP failures without exposing remote details."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.code = _classify_http_status(status)
        super().__init__(self.code)


class NoRedirectHTTPSConnection(HTTPSConnection):
    """HTTPS connection to a pinned IP with normal hostname TLS verification."""

    def __init__(
        self,
        host: str,
        pinned_ip: str,
        port: int,
        *,
        timeout: int,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self.pinned_ip = pinned_ip
        self.ssl_context = context

    def connect(self) -> None:
        original_host = self.host
        self.host = self.pinned_ip
        try:
            HTTPConnection.connect(self)
        finally:
            self.host = original_host
        if self.sock is None:
            raise OSError("provider_connection_failed")
        self.sock = self.ssl_context.wrap_socket(
            self.sock,
            server_hostname=original_host,
        )


def _safe_bearer_header(api_key: str) -> str:
    if "\r" in api_key or "\n" in api_key:
        raise ValidationError("credential_header_invalid")
    return f"Bearer {api_key}"


def _sanitize_detail(value: str) -> str:
    clean = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return clean[:240]


def _classify_http_status(status: int) -> str:
    if status == 402:
        return ModelConnection.Status.QUOTA_LIMITED
    if status in {401, 403}:
        return ModelConnection.Status.AUTH_INVALID
    if status == 404:
        return ModelConnection.Status.MODEL_UNAVAILABLE
    if status == 429:
        return ModelConnection.Status.RATE_LIMITED
    if 500 <= status <= 599:
        return ModelConnection.Status.DEGRADED
    return ModelConnection.Status.UNREACHABLE


def _json_request(
    method: str,
    url: str,
    *,
    api_key: str = "",
    payload: dict[str, Any] | None = None,
    timeout: int = PROBE_TIMEOUT_SECONDS,
    max_body_bytes: int = MAX_PROBE_BODY_BYTES,
    resolved_ips: tuple[str, ...],
) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise ValidationError("provider_endpoint_invalid")
    if parsed.port and parsed.port not in {443, 8443}:
        raise ValidationError("provider_port_forbidden")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    context = ssl.create_default_context()
    connection = NoRedirectHTTPSConnection(
        parsed.hostname,
        resolved_ips[0],
        parsed.port or 443,
        timeout=timeout,
        context=context,
    )
    headers = {"Accept": "application/json", "User-Agent": "MokshaAI/2"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = _safe_bearer_header(api_key)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(max_body_bytes + 1)
    finally:
        connection.close()
    if len(raw) > max_body_bytes:
        raise ValidationError("provider_body_too_large")
    payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
    if not isinstance(payload, dict):
        raise ValidationError("provider_response_invalid")
    return response.status, payload


def _json_get(
    url: str,
    api_key: str = "",
    *,
    resolved_ips: tuple[str, ...],
) -> tuple[int, dict[str, Any]]:
    return _json_request(
        "GET",
        url,
        api_key=api_key,
        resolved_ips=resolved_ips,
    )


def _stream_lines(
    url: str,
    *,
    api_key: str,
    payload: dict[str, Any],
    resolved_ips: tuple[str, ...],
) -> Iterator[bytes]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise ValidationError("provider_endpoint_invalid")
    if parsed.port and parsed.port not in {443, 8443}:
        raise ValidationError("provider_port_forbidden")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "text/event-stream, application/x-ndjson, application/json",
        "Content-Type": "application/json",
        "User-Agent": "MokshaAI/2",
    }
    if api_key:
        headers["Authorization"] = _safe_bearer_header(api_key)
    connection = NoRedirectHTTPSConnection(
        parsed.hostname,
        resolved_ips[0],
        parsed.port or 443,
        timeout=COMPLETION_TIMEOUT_SECONDS,
        context=ssl.create_default_context(),
    )
    total = 0
    try:
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        if response.status < 200 or response.status >= 300:
            response.read(MAX_PROBE_BODY_BYTES)
            raise ProviderRequestFailed(response.status)
        while True:
            line = response.readline(MAX_COMPLETION_BODY_BYTES + 1)
            if not line:
                break
            total += len(line)
            if total > MAX_COMPLETION_BODY_BYTES:
                raise ValidationError("provider_body_too_large")
            yield line
    finally:
        connection.close()


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
    except DecryptionFailed, KeyUnavailable:
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
        status, payload = _json_get(
            url,
            api_key,
            resolved_ips=validation.resolved_ips,
        )
    except TimeoutError, OSError, ssl.SSLError, json.JSONDecodeError, ValidationError:
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


def openai_chat_completion(
    *,
    connection: ModelConnection,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_output_tokens: int,
    on_delta: Callable[[str], None] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run one OpenAI-compatible completion safely."""

    validation = validate_public_https_endpoint(
        connection.endpoint_url,
        allow_private=connection.is_admin_connection,
        resolved_ips=connection.dns_pins or None,
    )
    api_key = connection.get_api_key()
    url = urljoin(f"{validation.normalized_url}/", "chat/completions")
    request_payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_output_tokens,
        "stream": on_delta is not None,
    }
    if on_delta is not None:
        request_payload["stream_options"] = {"include_usage": True}
        parts: list[str] = []
        usage: dict[str, Any] = {}
        for raw_line in _stream_lines(
            url,
            api_key=api_key,
            payload=request_payload,
            resolved_ips=validation.resolved_ips,
        ):
            line = raw_line.decode("utf-8").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if not isinstance(event, dict):
                raise ProviderResponseError("provider_response_invalid")
            reported_usage = event.get("usage")
            if isinstance(reported_usage, dict):
                usage = reported_usage
            choices = event.get("choices", [])
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0]
            delta = first.get("delta", {}) if isinstance(first, dict) else {}
            content = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(content, str) and content:
                parts.append(content)
                on_delta(content)
        if not parts:
            raise ProviderResponseError("provider_response_empty")
        return "".join(parts), usage

    status, payload = _json_request(
        "POST",
        url,
        api_key=api_key,
        timeout=COMPLETION_TIMEOUT_SECONDS,
        max_body_bytes=MAX_COMPLETION_BODY_BYTES,
        payload=request_payload,
        resolved_ips=validation.resolved_ips,
    )
    if status < 200 or status >= 300:
        raise ProviderRequestFailed(status)
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("provider_response_empty")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderResponseError("provider_response_invalid")
    message = first.get("message", {})
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ProviderResponseError("provider_response_invalid")
    usage = payload.get("usage", {})
    return message["content"], usage if isinstance(usage, dict) else {}


def ollama_chat_completion(
    *,
    connection: ModelConnection,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_output_tokens: int,
    on_delta: Callable[[str], None] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run one Ollama-compatible completion safely."""

    validation = validate_public_https_endpoint(
        connection.endpoint_url,
        allow_private=connection.is_admin_connection,
        resolved_ips=connection.dns_pins or None,
    )
    api_key = connection.get_api_key()
    url = urljoin(f"{validation.normalized_url}/", "api/chat")
    request_payload = {
        "model": model,
        "messages": messages,
        "stream": on_delta is not None,
        "options": {
            "temperature": temperature,
            "num_predict": max_output_tokens,
        },
    }
    if on_delta is not None:
        parts: list[str] = []
        usage: dict[str, Any] = {}
        for raw_line in _stream_lines(
            url,
            api_key=api_key,
            payload=request_payload,
            resolved_ips=validation.resolved_ips,
        ):
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ProviderResponseError("provider_response_invalid")
            message = event.get("message", {})
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str) and content:
                parts.append(content)
                on_delta(content)
            if event.get("done") is True:
                usage = {
                    key: event[key]
                    for key in [
                        "prompt_eval_count",
                        "eval_count",
                        "total_duration",
                        "load_duration",
                        "prompt_eval_duration",
                        "eval_duration",
                    ]
                    if key in event
                }
        if not parts:
            raise ProviderResponseError("provider_response_empty")
        return "".join(parts), usage

    status, payload = _json_request(
        "POST",
        url,
        api_key=api_key,
        timeout=COMPLETION_TIMEOUT_SECONDS,
        max_body_bytes=MAX_COMPLETION_BODY_BYTES,
        payload=request_payload,
        resolved_ips=validation.resolved_ips,
    )
    if status < 200 or status >= 300:
        raise ProviderRequestFailed(status)
    message = payload.get("message", {})
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ProviderResponseError("provider_response_invalid")
    usage = {
        key: payload[key]
        for key in [
            "prompt_eval_count",
            "eval_count",
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
        ]
        if key in payload
    }
    return message["content"], usage
