# LLM Platform

Purpose: provider-neutral model routing state for Moksha AI. This app stores user
connections, enabled model profiles, user model preferences, hardware scan
snapshots, and staff-triggered local installation jobs.

Data flow: browser and non-browser clients read sanitized connection/profile
status through `/api/v1/models/*`. Secrets are encrypted before persistence with
AES-256-GCM. Ciphertext AAD binds each API key to the user, connection ID, and
key version. User custom endpoints must be public HTTPS; private/local endpoints
are only valid for admin-owned built-in/local connections.

Entry points:

- `models.py`: persistent model platform objects.
- `security.py`: BYOK encryption and endpoint SSRF guardrails.
- `providers.py`: safe provider probes for OpenAI-compatible and Ollama-compatible endpoints.
- `services.py`: model selection precedence for chat override, user preference, fallback, and admin default.
- `views.py`: read-only status/profile APIs plus user preference update.
- `admin.py`: staff management surfaces.

Configuration:

- `MOKSHA_BYOK_MASTER_KEY`: base64-url encoded 32-byte AES key.
- `MOKSHA_BYOK_MASTER_KEY_FILE`: optional mounted file containing the same key.

Security notes:

- Missing or malformed BYOK master keys fail closed.
- API keys are never serialized by API responses or admin list views.
- Endpoint validation blocks credentials, non-HTTPS URLs, private, loopback,
  link-local, multicast, reserved, and unspecified addresses for user-owned
  connections.
- Remote data consent is required before saving user-owned remote connections.
- Provider probes do not follow redirects, do not use proxy environment variables,
  cap response bodies, and persist only sanitized status details.

Tests: `llm/tests/test_security.py` and `llm/tests/test_services.py`.

Related docs: root README, `chat/README.md`, and `deploy/README.md`.
