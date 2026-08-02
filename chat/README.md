# Chat Runs And Conversations

## Purpose

`chat/` owns conversations, cursor-paginated messages, durable generation runs,
attempt records, typed SSE replay, cancellation, and the application boundary
around retrieval and model execution.

## Architecture And Data Flow

Creating a run persists the user prompt and idempotency key, then queues a
dedicated Celery generation task. The worker resolves at most two model
attempts, retrieves qualified evidence when required, persists one final
assistant message, and publishes monotonic `state`, `delta`, `citation`,
`usage`, `error`, and `done` events to a one-hour Redis Stream. DB checkpoints
survive stream expiry and browser disconnects.

## Files And Entrypoints

- `models.py`: chats, messages, runs, attempts, and document chunks.
- `views.py`: chat/message pagination and run/SSE/cancel APIs.
- `tasks.py`: generation worker and bounded fallback.
- `events.py`: Redis Stream publication.
- `serializers.py`: request, citation, run, and event-adjacent schemas.
- `rag/`: corpus-neutral routing, retrieval, loading, and embeddings.

## Interfaces

- `POST /api/v1/chats/{chat_id}/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events`
- `POST /api/v1/runs/{run_id}/cancel`
- Cursor-paginated chat and message endpoints

Run creation requires `Idempotency-Key`. Deleting a chat with an active run
returns `409`. Overload returns `429` with `Retry-After`.

## Configuration

Configure Redis, the `generation` Celery queue, event TTL, retrieval thresholds,
context bounds, provider limits, and model defaults through Django settings.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache celery -A moksha worker -Q generation --loglevel=INFO
uv run --no-cache pytest chat/tests
```

## Tests

Coverage includes idempotency, active-run deletion, cancellation, Redis replay,
attempt fallback, citations, fail-closed routing, and persistence behavior.
Real integration requires PostgreSQL/PgVector, Redis, and Celery.

## Dependencies

Django, DRF, Celery, Redis, PostgreSQL/PgVector, `llm`, `scriptures`, and the
private embedding service.

## Security

APIs scope every record to the authenticated user. Public errors use stable
codes, never exception text. Synthetic error assistant messages are not
persisted. Citation fields are validated and bounded.

## Failure Modes And Troubleshooting

- SSE reconnect gap: fetch run state; DB holds final/checkpoint data.
- Cancel appears delayed: provider calls must honor bounded timeouts.
- No evidence: verify active qualified scripture index and similarity threshold.
- `429`: wait for `Retry-After`; generation concurrency is intentionally bounded.

## Related Docs

See `rag/README.md`, `../llm/README.md`, `../scriptures/README.md`, and
`../frontend/README.md`.
