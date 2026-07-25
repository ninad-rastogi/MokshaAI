# Embedding Service

## Purpose
Private single-process FastAPI sidecar intended to own the BGE-M3 embedding model once per deployment.

## Architecture And Data Flow
Django calls this service over the private Compose network. Caddy does not route public traffic to it.

## Files And Entrypoints
- `main.py`: FastAPI app with health and embedding endpoints.

## Interfaces
- `GET /health`
- `POST /embed` with JSON `{"texts": ["..."]}`

## Configuration
- `EMBEDDING_MODEL`
- `EMBEDDING_DEVICE`

## Commands
Run through Compose as `embedding`.

## Tests
Add API contract tests before switching Django retrieval fully to this sidecar.

## Dependencies
FastAPI, Uvicorn, sentence-transformers, torch.

## Security
No published ports. Do not expose through Caddy.

## Failure Modes And Troubleshooting
If the model cannot load, readiness must fail and Django should return a sanitized unavailable response.

## Related Docs
See `chat/rag/README.md` and the root README.
