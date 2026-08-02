<!-- moksha-readme-boundary:v1 -->
# operations/

## Purpose

Operational ownership for running, diagnosing, recovering, and maintaining Moksha AI. This
boundary records procedures; deployable configuration remains under `deploy/` and Compose files.

## Architecture And Data Flow

Caddy is the public edge. Requests flow to Nuxt or Django; Django uses PostgreSQL/pgvector,
Redis, Celery workers, the private embedding service, and host Ollama. Operational checks move
from edge health through application readiness to queue, database, model, and citation evidence.

## Files And Entrypoints

- `README.md`: current operational contract and troubleshooting index.
- `../docker-compose.yml`: service topology and health checks.
- `../deploy/Caddyfile`: edge routing.
- `../manage.py`: Django administration entrypoint.
- `../scripts/backup.ps1`: PostgreSQL custom dump plus corpus archive.
- `../scripts/restore.ps1`: guarded restore with pre-restore backup.
- `../scripts/generate_runtime_secrets.ps1`: one-time secret/keyring creation.

## Interfaces

Operators use Docker Compose, Django management commands, worker logs, and the
canonical edge endpoints `/api/v1/auth/health/`, `/api/v1/auth/ready/`, and
`/api/v1/auth/metrics/`. Metrics require staff session auth or
`X-Metrics-Token`. Caddy is the only published Compose service.

## Configuration

Runtime configuration comes from `.env` plus the ignored
`deploy/runtime-secrets/` files. `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`
are mandatory. `MOKSHA_BYOK_KEYRING_HOST_FILE` points to versioned AES keys;
`MOKSHA_METRICS_TOKEN` protects machine scraping. Disk and recovery thresholds
use `DISK_MIN_FREE_BYTES`, `JOB_STALE_MINUTES`, and
`MODEL_PART_MAX_AGE_HOURS`. Secrets must not enter logs or DB backups.

## Commands

```powershell
.\scripts\generate_runtime_secrets.ps1
docker compose up --build -d
docker compose ps
docker compose logs django generation-worker worker embedding
Invoke-RestMethod https://localhost:8443/api/v1/auth/health/
Invoke-RestMethod https://localhost:8443/api/v1/auth/ready/

.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupDirectory .\backups\<timestamp> -ConfirmRestore

$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run moksha security rewrap-byok --target-version 2
```

For key rotation, add a new random 32-byte URL-safe key to the keyring, set
`active_version`, mount both old and new versions, restart Django and generation
worker, run rewrap, verify every connection, then remove the old key only after
an encrypted backup. Rewrap is transactional. Never rotate by overwriting the
only old key.

## Tests

Verify health, readiness, authenticated metrics, scheduled recovery, disk
alerts, one Celery task per queue, embedding readiness, Ollama generation,
scripture index/rollback, and a cited RAG query. Stop and restart workers during
an active run to prove recovery. Restore a disposable backup and compare counts.
Record `docker stats --no-stream` at idle, generation, and indexing; target is
below 4 GiB steady and 6 GiB indexing, excluding host Ollama. Static Compose
reservations are not measured evidence.

## Dependencies

Docker Compose, Caddy, PostgreSQL with pgvector, Redis, Django, Celery, Nuxt, the embedding
service, and host Ollama. Python project dependencies are locked by `uv.lock`.

## Security

Keep PostgreSQL, Redis, Celery, Django, Nuxt, and the embedding service on the private Compose
network. Protect secrets and BYOK keys, keep remote-provider consent explicit, sanitize errors,
and preserve scripture-grounding and high-stakes safety controls.

## Failure Modes And Troubleshooting

- Readiness failure: inspect its component map, then `docker compose ps` and
  the named service logs.
- Stale queued/running job: verify Redis, worker queue, and scheduled
  `recover_stale_jobs`; durable checkpoints remain in PostgreSQL.
- Low disk: stop new indexing/install work, remove only task-created stale
  `.part` files, then expand storage or retention.
- Lost BYOK keyring: stop remote-provider generation, restore encrypted keyring,
  and verify decrypt. Do not reset keys or delete connections as a substitute.
- Suspected secret exposure: rotate Django/metrics credentials, rotate BYOK with
  rewrap, revoke provider keys, invalidate sessions, and preserve audit logs.
- `docker compose down -v` deletes database and indexed data; never use it as a
  routine recovery command.

## Related Docs

See [deployment](../deploy/README.md), [scripts](../scripts/README.md),
[RAG](../chat/rag/README.md), [embedding service](../embedding_service/README.md), and the
[project README](../README.md).
