"""Tests for chat API throttle scopes."""

from rest_framework.throttling import ScopedRateThrottle

from chat.views import ChatViewSet


def test_generation_run_creation_uses_chat_query_throttle_scope():
    view = ChatViewSet()
    view.action = "runs"

    throttles = view.get_throttles()

    assert len(throttles) == 1
    assert isinstance(throttles[0], ScopedRateThrottle)
    assert view.throttle_scope == "chat_query"
