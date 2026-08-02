# Transitional Streamlit Client

## Purpose

`streamlit_ui/` is the rollback-only legacy client. Nuxt is the product
frontend. Streamlit remains until Nuxt parity and rollback gates pass, then this
package, dependency, Compose profile, and related tests are removed atomically.

## Architecture And Data Flow

Streamlit calls Django over HTTP and does not import product backend internals.
It uses JWT compatibility intended for non-browser clients. It must not become a
second implementation of new product features.

## Files And Entrypoints

- `main_app.py`: legacy UI entry point.
- `api_client.py`: bounded Django API client.

## Interfaces

The client uses compatibility authentication, chat, and scripture endpoints.
Nuxt session/CSRF flows remain authoritative for browser production behavior.

## Configuration

Set the Django API base URL. The Compose service is disabled unless the
`legacy-streamlit` profile is selected.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache streamlit run streamlit_ui/main_app.py
docker compose --profile legacy-streamlit up streamlit
```

## Tests

Only regression tests needed for rollback remain. Production parity and
accessibility gates belong to `frontend/`.

## Dependencies

Streamlit and Requests. Both are transitional dependencies.

## Security

Tokens live only in Streamlit session state. Errors remain generic and must not
persist synthetic assistant messages or expose exception text.

## Failure Modes And Troubleshooting

- Authentication failure: verify compatibility JWT routes and API base URL.
- Missing feature: use Nuxt; new product behavior is not added here.
- Removal blocked: complete Nuxt parity, rollback, and live walkthrough gates.

## Related Docs

See `../frontend/README.md`, `../PRODUCT.md`, and `../deploy/README.md`.
