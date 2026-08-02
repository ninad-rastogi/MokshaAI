"""Redacted structured logging for services and workers."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization|api[_-]?key|token|password)=\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def redact(value: str) -> str:
    clean = value.replace("\r", " ").replace("\n", " ")
    for pattern in SECRET_PATTERNS:
        clean = pattern.sub("[REDACTED]", clean)
    return clean[:2000]


class JsonFormatter(logging.Formatter):
    """Render one bounded JSON object without exception strings."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        request_id = getattr(record, "request_id", "")
        if request_id:
            payload["request_id"] = str(request_id)[:80]
        exception_type = record.exc_info[0] if record.exc_info else None
        if exception_type is not None:
            payload["exception_type"] = exception_type.__name__
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
