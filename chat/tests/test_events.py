"""Unit tests for SSE event framing."""

from unittest.mock import Mock, patch

import pytest

from chat.events import (
    RUN_EVENT_TYPES,
    STREAM_TTL_SECONDS,
    format_sse,
    publish_run_event,
)


def test_format_sse_uses_id_event_and_compact_json_payload():
    rendered = format_sse(
        "2-0",
        "state",
        {"state": "running", "attempt_number": 1},
    )

    assert rendered == (
        'id: 2-0\nevent: state\ndata: {"state":"running","attempt_number":1}\n\n'
    )


def test_publish_run_event_allows_only_typed_generation_events():
    assert RUN_EVENT_TYPES == {
        "state",
        "delta",
        "citation",
        "usage",
        "error",
        "done",
    }
    with pytest.raises(ValueError, match="run_event_type_invalid"):
        publish_run_event("run:test", "message", {})


def test_publish_run_event_sets_one_hour_replay_ttl():
    client = Mock()
    client.xadd.return_value = "7-0"

    with patch("chat.events.redis_client", return_value=client):
        event_id = publish_run_event("run:test", "done", {"state": "completed"})

    assert event_id == "7-0"
    client.xadd.assert_called_once_with(
        "run:test",
        {"type": "done", "data": '{"state":"completed"}'},
        maxlen=2000,
        approximate=True,
    )
    client.expire.assert_called_once_with("run:test", STREAM_TTL_SECONDS)
