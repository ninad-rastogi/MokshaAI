# Session Authentication And Accounts

## Purpose

`users/` owns email-based accounts, browser session authentication, CSRF
bootstrap, registration, profile settings, theme persistence, logout, health,
and JWT compatibility for non-browser clients.

## Architecture And Data Flow

Nuxt first obtains a CSRF cookie, then submits credentials to Django. Successful
login or registration creates a Django session cookie. SSR and page refreshes
recover identity through `/api/v1/auth/me/`; browser bearer tokens are never
stored. JWT obtain/refresh routes remain separate for API clients.

## Files And Entrypoints

- `models.py`: custom email user and account preferences.
- `serializers.py`: registration/profile validation and stable field errors.
- `views.py`: session login/logout/register, CSRF, profile, and health.
- `urls.py`: versioned auth routing.
- `admin.py`: staff account management.

## Interfaces

Browser routes include CSRF bootstrap, register, login, logout, and current
profile. Duplicate registration returns a field-specific conflict that the UI
can render as an existing-account message.

## Configuration

Configure secure session/CSRF cookie flags, trusted origins, allowed hosts,
session lifetime, password validators, and HTTPS termination. Caddy must be the
published origin in production.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache pytest users/tests
uv run --no-cache python manage.py createsuperuser
```

## Tests

Coverage includes refresh persistence, duplicate registration, invalid
credentials, CSRF enforcement, logout, JWT compatibility, profile updates, and
theme persistence.

## Dependencies

Django auth, DRF, SimpleJWT, PostgreSQL, Nuxt session clients, and Caddy.

## Security

Passwords use Django hashing and validation. Sessions are HttpOnly and secure in
production. State-changing browser requests require CSRF. Responses never reveal
whether unrelated accounts exist beyond the explicit registration conflict.

## Failure Modes And Troubleshooting

- Refresh logs out: inspect session cookie domain, Secure/SameSite, and Caddy URL.
- CSRF failure: obtain the CSRF cookie and send `X-CSRFToken` on mutations.
- Duplicate registration: sign in or recover the existing account.
- Health fails: verify Django DB readiness rather than only process liveness.

## Related Docs

See `../frontend/README.md`, `../moksha/README.md`, `../deploy/README.md`, and
`../tests/README.md`.
