# Test And Evaluation Suite

## Purpose

`tests/` holds cross-app integration, browser, and versioned model-evaluation
coverage. App-local unit tests stay beside their owning Django app.

## Architecture And Data Flow

Backend tests use ephemeral PostgreSQL/PgVector fixtures and Redis/Celery where
the contract requires them. Browser tests exercise Caddy-facing session and
CSRF flows. LLM evaluations use versioned cases for routing, grounding,
citations, unsupported claims, safety, and multilingual context.

## Files And Entrypoints

- `e2e/`: deterministic browser/API journeys.
- `integration/`: cross-service backend flows.
- `evals/`: versioned LLM evaluation data and runners when present.
- `conftest.py`: shared fixtures and environment setup.

## Interfaces

Tests call public APIs whenever possible. Lower-level tests may use application
services and ports to isolate provider, retrieval, persistence, and event
behavior.

## Configuration

`moksha.settings_test` supplies test defaults. Real integration runs still need
PostgreSQL with the `vector` extension and Redis. Never point tests at
production data.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache pytest
uv run --no-cache pytest tests/e2e -m e2e
```

Frontend gates run from `frontend/` with `npm run test` and the Playwright
walkthrough described in `frontend/README.md`.

## Tests

Required release evidence includes unit tests, real database/queue integration,
deterministic browser E2E, accessibility checks, model evaluations, and a real
Compose/Caddy/Ollama qualification.

## Dependencies

pytest, pytest-django, pytest-asyncio, Playwright, Django, PostgreSQL/PgVector,
Redis, Celery, and configured model services.

## Security

Fixtures use synthetic accounts and secrets. Logs, snapshots, and reports must
not contain API keys, session cookies, or personal data.

## Failure Modes And Troubleshooting

- `type "vector" does not exist`: install/enable PgVector in the test database.
- Redis/Celery timeout: verify worker queue names and isolated Redis database.
- Browser auth failure: verify HTTPS origin, CSRF cookie, and Caddy trust.
- Model eval drift: record model/catalog versions before accepting new baselines.

## Related Docs

See `../README.md`, `../frontend/README.md`, `../deploy/README.md`, and
`../operations/README.md`.
