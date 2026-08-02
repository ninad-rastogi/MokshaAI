"""Focused tests for retrieval routing and citation prompt discipline."""

from langchain_core.messages import HumanMessage

from chat.rag.engine import RAGEngine


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _Classifier:
    def __init__(self, category: str) -> None:
        self.category = category

    def invoke(self, _messages: list[object]) -> _FakeResponse:
        return _FakeResponse(f'{{"category": "{self.category}", "reasoning": "test"}}')


class _VectorStore:
    def search(
        self,
        _query: str,
        top_k: int,
        allowed_scriptures: list[str],
    ) -> list[dict[str, object]]:
        assert top_k == 3
        assert allowed_scriptures == ["Library"]
        return [
            {
                "text": "Act without clinging to reward; keep attention on duty.",
                "scripture": "Library",
                "file_name": "teaching.pdf",
                "page": 12,
                "score": 0.91,
            }
        ]


def _engine() -> RAGEngine:
    engine = RAGEngine.__new__(RAGEngine)
    engine.vector_store = _VectorStore()
    engine.available_scriptures = ["Library"]
    engine.system_prompt = "Be grounded."
    engine.classifier_llm = _Classifier("GUIDANCE")
    return engine


def test_guidance_routes_to_retrieval_when_index_exists() -> None:
    engine = _engine()

    assert engine.route_query("How can I act without resentment?") == ("rag", True)


def test_rag_prompt_requires_exact_context_quote_and_real_sources(
    monkeypatch,
) -> None:
    engine = _engine()
    captured: list[HumanMessage] = []

    def complete(messages, _on_delta):
        captured.extend(msg for msg in messages if isinstance(msg, HumanMessage))
        return "Answer"

    monkeypatch.setattr(engine, "_complete", complete)

    _answer, sources = engine.query_with_rag("How can I act without resentment?")

    prompt = captured[-1].content
    assert "Source 1: Library, teaching.pdf, p. 12" in prompt
    assert "Start with a section named 'Source verse'" in prompt
    assert "Meaning" in prompt
    assert "Guidance" in prompt
    assert "Never cite, name, or invent a scripture" in prompt
    assert sources[0]["excerpt"] == (
        "Act without clinging to reward; keep attention on duty."
    )


def test_general_prompt_forbids_invented_scripture_citations(monkeypatch) -> None:
    engine = _engine()
    captured: list[HumanMessage] = []

    def complete(messages, _on_delta):
        captured.extend(msg for msg in messages if isinstance(msg, HumanMessage))
        return "Answer"

    monkeypatch.setattr(engine, "_complete", complete)

    engine.query_without_rag("Hi")

    prompt = captured[-1].content
    assert "Do NOT quote, cite, name, or invent scriptures" in prompt
    assert "unless they were explicitly provided in this message" in prompt
