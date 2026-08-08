"""Redis Stream event helpers for generation runs."""

import json
from typing import Any

from django.conf import settings
from redis import Redis

STREAM_TTL_SECONDS = 60 * 60
RUN_EVENT_TYPES = frozenset(
    {
        "state",
        "delta",
        "citation",
        "usage",
        "error",
        "done",
    }
)


def redis_client() -> Redis:
    return Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def publish_run_event(stream_key: str, event_type: str, data: dict[str, Any]) -> str:
    """Publish a typed event and keep one hour of replay."""
    if event_type not in RUN_EVENT_TYPES:
        raise ValueError("run_event_type_invalid")
    client = redis_client()
    event_id = client.xadd(
        stream_key,
        {"type": event_type, "data": json.dumps(data, separators=(",", ":"))},
        maxlen=2000,
        approximate=True,
    )
    client.expire(stream_key, STREAM_TTL_SECONDS)
    return str(event_id)


def format_sse(event_id: str, event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"
