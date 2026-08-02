# Retrieval And Grounded Guidance

## Purpose

`chat/rag/` provides corpus-neutral safety routing, retrieval, grounded-answer
construction, PDF loading, semantic chunking, and PgVector access. It never
assumes a fixed scripture title or one historical guide.

## Architecture And Data Flow

Available collections come from active scripture index data. A typed router
selects safety, retrieval, or general guidance. Retrieval searches only the
active qualified version, filters by minimum evidence quality, bounds context,
and returns validated citation records. Weak or absent evidence produces an
honest no-evidence response instead of unsupported scripture claims.

## Files And Entrypoints

- `engine.py`: routing and grounded/general response construction.
- `embeddings.py`: PgVector search and private embedding calls.
- `loader.py`: dynamic PDF collection loading.
- `chunker.py`: semantic chunks with language and source metadata.

## Interfaces

`RAGEngine` exposes routing and response methods to the chat application worker.
`PgVectorStore` exposes bounded search and indexing operations. Returned sources
contain collection, file, page, score, and excerpt fields.

## Configuration

Set embedding service URL, active index version, similarity threshold, maximum
retrieval count, context character/token limits, and document root.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache pytest chat/tests/test_safety.py
uv run --no-cache python manage.py discover_scriptures
```

## Tests

Versioned evaluations cover routing, citation JSON, grounding, unsupported
claims, safety, and English/Hindi/Sanskrit context. Real retrieval smoke tests
require PgVector and the private BGE-M3 service.

## Dependencies

PostgreSQL/PgVector, PyMuPDF, LangChain message types, Django settings, Ollama
or a selected provider, and the embedding sidecar.

## Security

Raw HTML is unrelated to this backend path and never trusted. Context is
bounded, file paths are not exposed, prompt construction separates system,
history, evidence, and user input, and provider exceptions remain private.

## Failure Modes And Troubleshooting

- Empty search: verify active complete index and collection annotations.
- Low scores: inspect embedding model/version parity and retrieval threshold.
- Invalid citation: reject response data rather than coercing untrusted fields.
- PDF parse failure: inspect sanitized loader logs and source integrity.

## Related Docs

See `../README.md`, `../../scriptures/README.md`,
`../../embedding_service/README.md`, and `../../tests/README.md`.
