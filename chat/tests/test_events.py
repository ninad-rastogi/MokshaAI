"""Unit tests for SSE event framing."""

from chat.events import format_sse


def test_format_sse_uses_id_event_and_compact_json_payload():
    rendered = format_sse(
        "2-0",
        "state",
        {"state": "running", "attempt_number": 1},
    )

    assert rendered == (
        'id: 2-0\nevent: state\ndata: {"state":"running","attempt_number":1}\n\n'
    )
