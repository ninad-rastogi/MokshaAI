<!-- moksha-readme-boundary:v1 -->
# scripts/

## Purpose

Repository-local maintenance and verification commands. Scripts are explicit tools, not
application services, and must avoid hidden changes to source or Git state.

## Architecture And Data Flow

Commands read repository configuration or call existing project tools. README validation
discovers architectural boundaries, reads Markdown, and returns diagnostics. Scaffolding takes
one operator-selected directory and writes only that directory's `README.md`.

## Files And Entrypoints

- `validate_readmes.py`: read-only boundary and documentation validator.
- `scaffold_readme.py`: opt-in generator for one canonical boundary README.
- `run_frontend_gate.py`: adapter for frontend quality commands.
- `run_python_gate.py`: resolves the active or shared ancestor Python environment.
- `benchmark_ollama.py`: local Ollama qualification benchmark.
- `live_ui_walkthrough.py`: browser walkthrough evidence command.
- `export_openapi.py`: canonical v1 schema and stable operation IDs.
- `generate_runtime_secrets.ps1`: one-time Django, DB, metrics, BYOK secrets.
- `backup.ps1` and `restore.ps1`: guarded DB/corpus recovery workflow.
- `trust_caddy_local_ca.ps1`: narrow local CA trust helper.

## Interfaces

Both README tools expose command-line interfaces and return `0` on success, `1` for validation
findings, and `2` for invalid command input. The validator also exposes typed `validate()` and
`discover_boundaries()` functions for focused tests.

## Configuration

Tools use Python 3.14 and the standard library. `--root` overrides repository discovery. The
validator accepts `--warnings-as-errors` for strict legacy-document migration checks.
Python hooks prefer `VIRTUAL_ENV`, then the nearest ancestor `.env`, and never
create a project `.venv`.

## Commands

```powershell
python scripts/validate_readmes.py --root .
python scripts/validate_readmes.py --root . --warnings-as-errors
python scripts/scaffold_readme.py <opt-in-boundary> --root .
python scripts/export_openapi.py --output frontend/openapi.json
python scripts/benchmark_ollama.py --models <ollama-tag> --min-tokens-per-second 20
python scripts/live_ui_walkthrough.py --base-url https://localhost:8443/
.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupDirectory <path> -ConfirmRestore
```

Scaffolding is never called by pre-commit or CI. It refuses existing READMEs, paths outside the
repository, symlinks, excluded folders, data-only folders, and trivial folders.

## Tests

Run `python scripts/validate_readmes.py --help`, `python scripts/scaffold_readme.py --help`, and
`python scripts/validate_readmes.py --root .`. Focused temporary-directory tests may import the
typed validator functions without Django or third-party packages.

## Dependencies

README tools use Python 3.14 standard library only. OpenAPI export needs Django
runtime dependencies. Browser walkthrough needs Playwright/Chrome. Model
benchmark needs Requests and host Ollama; it reports functional pass,
throughput pass, configured target, measured safe minimum, and median tokens per
second while exiting fail-closed when the selected model misses the target.
Backup/restore need PowerShell, Docker Compose, PostgreSQL tools inside DB
container.

## Security

Targets are resolved before use and must remain inside the repository. Symlinks and excluded
trees are rejected. Validator link checks reject relative paths that escape the repository.
Documentation hooks never invoke Git, download content, create READMEs, or
stage files. Runtime secret script refuses overwrite. Restore requires explicit
confirmation and creates pre-restore backup. Browser evidence must use synthetic
accounts and never persist cookies/API keys in reports.

## Failure Modes And Troubleshooting

Exit `1` means validation found an error, or a warning under `--warnings-as-errors`. Exit `2`
means the root or scaffold target is invalid. Scaffold placeholders intentionally fail strict
validation until replaced with boundary-specific content.

## Related Docs

See [operations documentation](../operations/README.md), [deployment](../deploy/README.md), and
the [project README](../README.md).
