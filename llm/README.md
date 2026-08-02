# Provider-Neutral Model Platform

## Purpose

`llm/` owns model connections, profiles, account preferences, host hardware
snapshots, and staff-controlled local installation records. Product code does
not assume one provider or one scripture collection.

## Architecture And Data Flow

Users may add public HTTPS OpenAI-compatible or Ollama-compatible endpoints with
explicit remote-data consent. Admin-owned built-in Ollama stays private.
Selection precedence is chat override, user primary, one eligible fallback, then
admin local default. Each generation attempt stores an immutable provider/model
snapshot.

## Files And Entrypoints

- `models.py`: connections, profiles, preferences, hardware scans, install jobs.
- `security.py`: AES-256-GCM envelopes and SSRF validation.
- `providers.py`: bounded provider probes and completion adapters.
- `services.py`: deterministic model selection.
- `views.py`: sanitized user APIs.
- `admin.py`: staff controls.
- `catalog.py`: signature, monotonic release, checksum, and revocation checks.
- `tasks.py`: resumable download, Ollama import, qualification, cleanup.

## Interfaces

Versioned APIs expose sanitized connections, selectable profiles, probes,
preference updates, catalog releases, and staff-only install jobs. Secrets are
write-only. V1 dialects are OpenAI-compatible, Ollama-compatible, and built-in
Ollama. Only one install job may run, and enabling an installed profile never
changes account preferences or the admin default.

## Configuration

Mount `MOKSHA_BYOK_KEYRING_FILE` outside DB. Keyring contains
`active_version` and versioned 32-byte keys. Configure private Ollama, request
limits, local concurrency 1, remote concurrency 4, imports bind mount, and
signed catalog before enabling installation.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache python manage.py check
uv run --no-cache pytest llm/tests
uv run moksha setup model scan --context-length 8192
uv run moksha security rewrap-byok --target-version 2
uv run python scripts/benchmark_ollama.py --models <temporary-qualified-tag>
```

Host hardware discovery belongs to the optional `moksha setup model scan`
command and must never run in Django containers.

## Tests

Coverage includes encryption/rewrap fail-closed behavior, DNS pinning and SSRF
guards, provider statuses, preference precedence, revocation, install checksum
and cleanup, signed catalog replay controls, qualification, and attempt fallback
limits. Real activation still requires structured JSON, multilingual, citation,
grounding, safety, 8K context, throughput, and memory tests against host Ollama.

## Dependencies

Django, DRF, Cryptography, Requests/HTTP transport, and provider APIs.

## Security

BYOK uses versioned AES-256-GCM with AAD binding user, connection, and key
version. Requests reject unsafe addresses, redirects, proxy inheritance,
credentials in URLs, unsafe headers, and oversized responses. Missing keys fail
closed.

## Failure Modes And Troubleshooting

- `auth_invalid`: replace or revoke the provider key.
- `endpoint_invalid`: use a public HTTPS endpoint allowed by policy.
- `unreachable`: inspect DNS pins and bounded probe detail.
- Missing key version: restore matching mounted key before decrypting or
  rewrapping; DB rollback cannot recover it.
- Stale hardware profile: run the explicit host scan again.
- Install checksum/signature failure: retain existing models/defaults, clean
  task-created temporary artifacts, and reject activation.
- Provider may bill failed attempt: disclose this before enabling fallback.

## Related Docs

See `../chat/README.md`, `../operations/README.md`, `../deploy/README.md`, and
`../frontend/README.md`.
