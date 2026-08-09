"""Unit tests for the private embedding sidecar contract."""

from fastapi.testclient import TestClient

from embedding_service import main


class _Vector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class _FakeModel:
    def get_embedding_dimension(self) -> int:
        return 3

    def encode(
        self,
        texts: list[str],
        *,
        show_progress_bar: bool,
        normalize_embeddings: bool,
    ) -> list[_Vector]:
        assert show_progress_bar is False
        assert normalize_embeddings is True
        return [_Vector([0.1, 0.2, 0.3]) for _text in texts]


def test_embedding_service_reuses_single_loaded_model(monkeypatch):
    created: list[tuple[str, str]] = []

    def fake_transformer(model_name: str, *, device: str) -> _FakeModel:
        created.append((model_name, device))
        return _FakeModel()

    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING_DEVICE", "cpu")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "3")
    monkeypatch.setattr(main, "SentenceTransformer", fake_transformer)
    main.model.cache_clear()
    with TestClient(main.app) as client:
        assert created == [("BAAI/bge-m3", "cpu")]
        ready = client.get("/ready")
        embedded = client.post("/embed", json={"texts": ["steadiness", "clarity"]})

    assert ready.status_code == 200
    assert embedded.status_code == 200
    assert embedded.json() == {
        "embeddings": [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]],
        "model": "BAAI/bge-m3",
    }
    assert created == [("BAAI/bge-m3", "cpu")]

    main.model.cache_clear()
