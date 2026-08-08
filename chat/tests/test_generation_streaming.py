"""Tests that unsafe ungrounded text is buffered before browser emission."""

from types import SimpleNamespace
from typing import Any, cast

from chat.tasks import (
    GenerationAttemptSpec,
    _emit_sanitized_deltas,
    _generate_remote_provider_response,
    _generate_response,
)
from llm.models import ModelConnection


class _GeneralEngine:
    def __init__(self, **_kwargs: Any) -> None:
        self.vector_store = object()

    def route_query(self, _query: str) -> tuple[str, bool]:
        return "general", False

    def query_without_rag(
        self,
        _query: str,
        _messages: list[dict[str, Any]],
        on_delta,
    ) -> str:
        if on_delta:
            on_delta("Fake answer. (From The Book of Life, File: Wisdom, Page 34)")
        return "Fake answer. (From The Book of Life, File: Wisdom, Page 34)"


def _spec(provider: str = "ollama") -> GenerationAttemptSpec:
    return GenerationAttemptSpec(
        provider=provider,
        model="test-model",
        ollama_server="http://ollama.test",
        connection=cast(ModelConnection, object()),
        temperature=0.7,
        max_output_tokens=128,
        snapshot={},
    )


def test_local_general_generation_buffers_before_grounding(monkeypatch) -> None:
    deltas: list[str] = []
    monkeypatch.setattr("chat.tasks.PgVectorStore", lambda: object())
    monkeypatch.setattr("chat.tasks.RAGEngine", _GeneralEngine)

    response, sources, mode = _generate_response(
        run=cast(Any, SimpleNamespace(prompt="How can I act without resentment?")),
        spec=_spec(),
        recent_messages=[],
        available_scriptures=["Library"],
        on_delta=deltas.append,
    )

    assert mode == "GENERAL"
    assert sources == []
    assert "The Book of Life" not in response
    assert "no indexed source evidence was used" in response
    assert deltas == []


def test_remote_general_generation_buffers_before_grounding() -> None:
    deltas: list[str] = []

    def fake_completion(**kwargs):
        on_delta = kwargs["on_delta"]
        if on_delta:
            on_delta("Fake answer. (From The Book of Life, File: Wisdom, Page 34)")
        return (
            "Fake answer. (From The Book of Life, File: Wisdom, Page 34)",
            {"total_tokens": 7},
        )

    response, sources, mode = _generate_remote_provider_response(
        completion_func=fake_completion,
        run=cast(Any, SimpleNamespace(prompt="Offer guidance.")),
        spec=_spec(ModelConnection.Dialect.OPENAI_COMPATIBLE),
        recent_messages=[],
        available_scriptures=[],
        on_delta=deltas.append,
    )

    assert mode == "GENERAL"
    assert sources == []
    assert "The Book of Life" not in response
    assert "no indexed source evidence was used" in response
    assert deltas == []


def test_sanitized_final_text_emits_in_bounded_chunks() -> None:
    deltas: list[str] = []
    text = "Validated guidance. " * 25

    _emit_sanitized_deltas(text, deltas.append, chunk_size=80)

    assert len(deltas) > 1
    assert "".join(deltas) == text
    assert all(len(delta) <= 80 for delta in deltas)
