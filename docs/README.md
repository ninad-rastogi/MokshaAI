# Architecture Documentation

## Purpose

`docs/` holds durable cross-service decisions and generated API references that
do not belong to one deployable service.

## Architecture And Data Flow

Documents describe the Caddy, Nuxt, Django, Celery, Redis, PostgreSQL/PgVector,
private embedding-sidecar, and host-Ollama boundaries. Source code and tests
remain authoritative when prose drifts.

## Files And Entrypoints

Add architecture decisions, API lifecycle notes, threat models, and evaluated
operational procedures here. Keep product intent in `PRODUCT.md`, visual rules
in `DESIGN.md`, and service commands in boundary READMEs.

- `project-graph.md`: compact current architecture graph for handoff and
  token-efficient navigation.

## Interfaces

OpenAPI is generated from Django/DRF and consumed by the frontend type
generation step. SSE remains a hand-written schema-validated adapter.

## Configuration

Documentation commands use the required Python environment and checked-in
frontend lockfile. Generated outputs must identify their source command.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache python scripts/validate_readmes.py
```

## Tests

README validation checks required sections, boundary coverage, placeholders,
duplicate content, broken relative links, and missing references. CI and
pre-commit only validate; they never create or stage files.

## Dependencies

Project source, generated OpenAPI artifacts, and the standard-library README
validator.

## Security

Do not include live credentials, internal DNS data, session values, personal
information, or decrypted provider keys in documentation or examples.

## Failure Modes And Troubleshooting

- Broken link: use a path relative to the document containing it.
- Stale API example: regenerate types/schema and update the owning service docs.
- Missing boundary README: run the explicit scaffold command, edit all
  placeholders, then rerun validation.

## Related Docs

See `project-graph.md`, `../README.md`, `../PRODUCT.md`, `../DESIGN.md`,
`../operations/README.md`, and `../scripts/README.md`.
