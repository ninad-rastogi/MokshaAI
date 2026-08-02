# Deployment

## Purpose
Production-oriented local deployment assets for Moksha AI.

## Architecture And Data Flow
Caddy is the only public edge in the Compose deployment. It routes `/api/v1/*`, `/admin/*`, and `/static/*` to Django ASGI/Uvicorn, and all other paths to Nuxt.

## Files And Entrypoints
- `Caddyfile`: edge routing for Django and Nuxt.
- `ollama/Modelfile.qwen3-4b-instruct-q3km`: local model import recipe.
- `model_catalog/`: signed, versioned, checksum-pinned install catalog.
- `../docker-compose.yml`: private production-shaped service topology.
- `../docker-compose.test.yml`: opt-in loopback PostgreSQL publication for tests.

## Interfaces
Publish Caddy HTTPS on `CADDY_HTTPS_PORT`, default `8443`. Django, Nuxt,
Redis, PostgreSQL, Celery, and embedding stay private. Caddy sends
`/api/v1/*`, `/admin/*`, and `/static/*` to Django; all other paths go to Nuxt.

## Configuration
Use `.env` and ignored runtime secret files. Compose refuses to start without
`DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. Mount BYOK keyring read-only into
only Django and generation worker. Bind Ollama imports to
`D:/Softwares/Ollama/Imports`; Ollama models remain under
`D:/Softwares/Ollama/Models` on Windows host.

## Commands
```powershell
.\scripts\generate_runtime_secrets.ps1
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs django generation-worker worker model-installer embedding
```

## Tests
Run Django checks and integration tests against real Compose PgVector/Redis.
For host DB/Redis tests only, add `-f docker-compose.test.yml`; publication binds
to `127.0.0.1`, never all interfaces. Qualify Caddy session/CSRF, SSE replay,
host Ollama, model install, indexing rollback, and measured memory.

## Dependencies
Docker Compose, Caddy, PostgreSQL pgvector, Redis, Django, Nuxt, Celery, and host Ollama.

## Security
Do not add `ports` to internal services. Keep model catalog public key in code,
but private signing key outside repository. Reject invalid, replayed, revoked,
or downgraded catalogs. Trust local Caddy CA narrowly; do not disable endpoint
protection. Never run `docker compose down -v` unless destroying persisted data.

## Failure Modes And Troubleshooting
- Port conflict: set `CADDY_HTTPS_PORT`; only test override uses
  `POSTGRES_HOST_PORT`.
- Caddy 502: check Django/Nuxt health and private DNS names.
- Browser cookie/CSRF failure: access one HTTPS origin and verify trusted origin
  settings; never bypass with local-storage JWT.
- Missing keyring mount: generate or restore secret file before Compose startup.

## Related Docs
See the root README, `frontend/README.md`, `chat/README.md`, and `embedding_service/README.md`.
