# Django Project Configuration

## Purpose

`moksha/` configures the Django 6 product backend. It owns settings, root URL
routing, Celery bootstrap, and ASGI/WSGI entry points. Product APIs remain in
their owning Django apps.

## Architecture And Data Flow

Caddy sends `/api/v1/*`, `/admin/*`, and `/static/*` traffic to Django. Uvicorn
loads `moksha.asgi:application`. Django uses PostgreSQL/PgVector for durable
state, Redis for Celery and run events, the private embedding service for
BGE-M3, and configured model providers for generation.

## Files And Entrypoints

- `settings.py`: environment-backed runtime settings and security policy.
- `settings_test.py`: isolated test overrides.
- `urls.py`: root API, admin, and health routes.
- `asgi.py`: production ASGI entry point.
- `wsgi.py`: compatibility entry point for management tooling.
- `celery.py`: Celery application and queue routing.

## Interfaces

Root routes delegate to `users`, `chat`, `scriptures`, and `llm`. Django admin
is available under `/admin/`. Browser authentication uses Django session
cookies and CSRF; JWT remains available for non-browser clients.

## Configuration

Required production values include PostgreSQL and Redis URLs,
`DJANGO_SECRET_KEY`, allowed hosts, CSRF trusted origins, Ollama settings, and
the BYOK master-key file. See `.env.example` and `deploy/README.md`.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache python manage.py check
uv run --no-cache python manage.py migrate
uv run --no-cache uvicorn moksha.asgi:application --host 0.0.0.0 --port 8000
```

## Tests

Run `python manage.py check`, migration drift checks, mypy, and pytest through
`uv` in the required environment. Integration tests require PostgreSQL with
PgVector and Redis.

## Dependencies

Django, DRF, SimpleJWT, Celery, Redis, PostgreSQL/PgVector, and Uvicorn.

## Security

Production settings fail closed for missing secrets, restrict hosts and trusted
origins, preserve secure session/CSRF cookies, and never expose the embedding
service directly.

## Failure Modes And Troubleshooting

- Database startup failures: verify PostgreSQL and the `vector` extension.
- Queue failures: verify Redis and Celery generation/index workers.
- CSRF failures: verify Caddy origin, trusted origins, and cookie attributes.
- Missing BYOK key: mount the configured key file; remote keys stay unusable.

## Related Docs

See `../README.md`, `../deploy/README.md`, `../operations/README.md`, and each
Django app README.
