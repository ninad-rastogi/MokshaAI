# Deployment

## Purpose
Production-oriented local deployment assets for Moksha AI.

## Architecture And Data Flow
Caddy is the only public edge in the Compose deployment. It routes `/api/v1/*`, `/admin/*`, and `/static/*` to Django ASGI/Uvicorn, and all other paths to Nuxt.

## Files And Entrypoints
- `Caddyfile`: edge routing for Django and Nuxt.
- `ollama/Modelfile.qwen3-4b-instruct-q3km`: local model import recipe.

## Interfaces
Publish Caddy on `CADDY_HTTP_PORT`, default `8080`. Django, Nuxt, Redis, Postgres, Celery, and embedding services stay on the private Compose network unless explicitly overridden.

## Configuration
Use `.env` for Compose variables such as `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `OLLAMA_MODEL`, and host model/cache paths.

## Commands
- `docker compose up --build -d`
- `docker compose ps`
- `docker compose logs django generation-worker worker`

## Tests
Run Django checks and integration tests against the Compose pgvector database before treating the stack as ready.

## Dependencies
Docker Compose, Caddy, PostgreSQL pgvector, Redis, Django, Nuxt, Celery, and host Ollama.

## Security
Do not expose the embedding service directly. Keep Caddy as the only public edge. Never run `docker compose down -v` unless you intend to remove persistent database and index data.

## Failure Modes And Troubleshooting
If tests connect to a local PostgreSQL instead of Compose, set `POSTGRES_HOST_PORT` to a free port such as `55432` and run tests with `POSTGRES_PORT=55432`.

## Related Docs
See the root README, `frontend/README.md`, `chat/README.md`, and `embedding_service/README.md`.
