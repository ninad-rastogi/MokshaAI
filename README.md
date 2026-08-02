<!-- moksha-readme-boundary:v1 -->
# Moksha AI

## Purpose

Moksha AI is a self-hosted spiritual guidance product for difficult moments.
It listens without judgment, retrieves relevant teachings from an expandable
library of Indian spiritual texts, and keeps cited evidence separate from its
own counsel. No product path assumes one scripture, teacher, dialogue, or PDF.

Nuxt is the primary client. Legacy Streamlit remains behind an opt-in Compose
profile until real Caddy, recovery, accessibility, and cited-RAG parity gates
pass; its later removal must be one atomic change.

## Architecture And Data Flow

```text
Browser
  |
  | HTTPS, Django session cookie, CSRF
  v
Caddy (only published port)
  |-- /api/v1/*, /admin/*, /static/* --> Django 6 + DRF + Uvicorn
  `-- everything else ----------------> Nuxt 4 SSR

Django --> PostgreSQL + PgVector     durable product and retrieval state
       --> Redis Streams             one-hour typed SSE replay
       --> Celery generation queue   durable, disconnect-safe generation
       --> Celery indexing queue     candidate index build and qualification
       --> Celery operations queue   recovery, disk, and cleanup jobs
       --> private FastAPI sidecar    one BGE-M3 owner
       --> Windows-host Ollama        local generation
       --> public HTTPS providers     consented encrypted BYOK connections
```

Each request uses one durable `GenerationRun` and at most two immutable
`GenerationAttempt` records. Typed events are `state`, `delta`, `citation`,
`usage`, `error`, and `done`. Browser disconnect does not stop generation;
explicit cancellation does. Fallback is allowed only before first token.

Indexing discovers every first-level directory containing PDFs, including
nested volume directories. It builds an immutable candidate version, qualifies
counts and real retrieval, then activates transactionally while retaining the
prior complete version for rollback.

## Files And Entrypoints

- `frontend/`: Nuxt 4, Vue 3, strict TypeScript product UI.
- `moksha/`: Django settings, ASGI, logging, middleware, CLI, operations.
- `users/`: session/CSRF auth, JWT compatibility, account settings.
- `chat/`: chats, messages, generation lifecycle, SSE, citations, routing.
- `chat/rag/`: PDF discovery, chunking, retrieval, embedding, prompts.
- `scriptures/`: immutable index versions, jobs, qualification, rollback.
- `llm/`: providers, profiles, preferences, catalog, local installation.
- `embedding_service/`: private single-process BGE-M3 FastAPI service.
- `deploy/`: Caddy and signed local-model catalog assets.
- `operations/`: backup, restore, rotation, recovery, incident procedures.
- `scripts/`: maintenance, generation, benchmark, and audit tools.
- `tests/`: cross-service, browser, operations, and model evaluations.
- `PRODUCT.md`: product intent and safety boundaries.
- `DESIGN.md`: interaction, responsive, visual, accessibility contract.

## Interfaces

Canonical APIs live under `/api/v1/`. Important contracts:

- `POST /api/v1/auth/session/login/` and `/session/logout/`
- `GET /api/v1/auth/me/` and `/csrf/`
- `GET|POST /api/v1/chats/`
- `GET|PATCH|DELETE /api/v1/chats/{chat_id}/`
- `GET /api/v1/chats/{chat_id}/messages/`
- `POST /api/v1/chats/{chat_id}/runs/` with `Idempotency-Key`
- `GET /api/v1/runs/{run_id}/`
- `GET /api/v1/runs/{run_id}/events/` with `Last-Event-ID`
- `POST /api/v1/runs/{run_id}/cancel/`
- `/api/v1/models/*` for profiles, preferences, connections, installs
- `/api/v1/scriptures/*` for status, versions, reindex, rollback

Browser code never stores bearer tokens. JWT remains for non-browser clients.
`frontend/openapi.json` contains canonical v1 REST routes; generated types live
in `frontend/types/openapi.d.ts`. SSE decoding stays handwritten and validated.

## Configuration

Use Python 3.14 through `uv` and the required environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
$env:UV_CACHE_DIR = (Resolve-Path '.tmp\uv-cache').Path
```

Create runtime secrets once, then load
`deploy/runtime-secrets/runtime.env` for Compose:

```powershell
.\scripts\generate_runtime_secrets.ps1
Get-Content .\deploy\runtime-secrets\runtime.env
```

Never regenerate a BYOK keyring after storing remote keys. Back up keyring and
runtime environment in an encrypted secret store separate from DB backups.
See `.env.example` and `operations/README.md` for all settings and rotation.

## Commands

Install locked dependencies without replacing unrelated packages in the shared
environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv sync --locked --inexact --extra dev --extra model-setup
Push-Location frontend
npm ci
npm run generate:types
Pop-Location
```

Start production-shaped local services and open `https://localhost:8443`:

```powershell
docker compose up --build -d
docker compose ps
```

Index every discovered collection and optionally scan host hardware:

```powershell
uv run python manage.py discover_scriptures
uv run moksha setup model scan --context-length 8192
uv run python scripts/benchmark_ollama.py --models <qualified-ollama-tag>
```

## Tests

Core gates:

```powershell
uv run black --check .
uv run ruff check .
uv run mypy moksha users chat scriptures llm embedding_service scripts
uv run python manage.py check --deploy
uv run python manage.py makemigrations --check --dry-run
uv run pytest

Push-Location frontend
npm run format
npm run lint
npm run stylelint
npm run typecheck
npm run test
npm run build
Pop-Location
```

Primary Compose publishes only Caddy. Host integration tests can add the
loopback-only PostgreSQL override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d db redis
$env:POSTGRES_PORT = '55432'
$env:REDIS_URL = 'redis://localhost:56379/0'
uv run pytest
```

Release evidence also needs live Chrome and axe walkthroughs, real
Compose/Caddy/Ollama qualification, multilingual LLM evaluations, restart
recovery, backup/restore, secret-loss drills, and measured memory.

## Dependencies

Runtime uses Django 6, DRF, Uvicorn, PostgreSQL/PgVector, Redis, Celery,
FastAPI, BGE-M3, Ollama or compatible providers, Nuxt 4, Vue 3, Nuxt UI 4,
and Caddy. Python is locked in `uv.lock`; frontend in
`frontend/package-lock.json`.

WhichLLM is optional Windows-host setup code. Django containers never import
it or scan hardware. BGE-M3 belongs only to private embedding service.

## Security

Caddy is sole published Compose port. Browser auth uses secure session cookies
and CSRF. Raw HTML is disabled in Markdown and rendered output is sanitized.

BYOK keys use versioned AES-256-GCM with AAD binding to user and connection.
Custom endpoints require explicit consent and public HTTPS. Requests pin
validated DNS, reject private and metadata ranges, disable redirects and proxy
inheritance, cap ports/time/body, and allow only safe headers. Logs and errors
expose stable sanitized codes, never secrets or exception strings.

Safety routing fails closed and never invents scripture evidence. Missing
qualified evidence produces an honest no-evidence response. Spiritual guidance
is not emergency, medical, legal, or financial authority.

## Failure Modes And Troubleshooting

- Refresh signs out: verify Caddy origin, session and CSRF cookies, and
  `/api/v1/auth/me/`; never fall back to browser bearer storage.
- `type "vector" does not exist`: enable PgVector in actual test database.
- Generation stays queued: inspect generation worker, Redis, durable run state.
- Embedding is unready: inspect model cache, disk, memory, and sidecar logs.
- Local generation fails: verify host Ollama and exact enabled profile tag.
- BYOK decrypt fails: restore matching keyring before rewrap. DB-only backup
  cannot recover encrypted keys.
- Local HTTPS is blocked: narrowly trust Caddy CA. Never disable Kaspersky or
  create broad endpoint-protection exclusions.
- `docker compose down -v` destroys DB and index volumes. Never use for restart.

## Related Docs

Read `PRODUCT.md` and `DESIGN.md` first. See `operations/README.md` for runbooks,
`deploy/README.md` for topology, and each service/domain README listed above.
