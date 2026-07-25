# moksha/ — Django Project Package

This is the **main Django project package**. It contains the core configuration, URL routing,
and WSGI/ASGI entry points for the Django application.

## Files

### `settings.py`
The **central configuration file** for the entire Django backend. Everything the Django app
needs is configured here:

- **Environment variables**: Loads from `.env` via `python-dotenv`
- **Installed apps**: Django admin, DRF, CORS, and local apps (`users`, `chat`, `scriptures`)
- **Database**: PostgreSQL configured via `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, etc.
- **REST Framework**: JWT authentication via `djangorestframework-simplejwt`, pagination
  (20 items/page), throttling (1000 requests/hour per user)
- **SimpleJWT settings**: Access token lifetime (1 hour), refresh token lifetime (7 days),
  token rotation enabled
- **CORS**: Allows requests from `http://localhost:8501` (Streamlit frontend)
- **Ollama/RAG settings**: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `EMBEDDING_MODEL` (BAAI/bge-m3),
  `VEDIC_SYSTEM_PROMPT` (the full system prompt for the AI)
- **Logging**: Structured logging for `moksha`, `chat`, `users`, `scriptures` loggers
- **Base directories**: `BASE_DIR`, `DATA_DIR`, `DOCS_DIR`, `EMBEDDINGS_DIR` — auto-created on
  startup

### `urls.py`
The **root URL router** that maps URL prefixes to each Django app:

| URL Pattern | App | Description |
|-------------|-----|-------------|
| `/admin/` | Django admin | Web-based admin panel |
| `/api/auth/` | `users` | Authentication endpoints |
| `/api/chat/` | `chat` | Chat CRUD and query endpoints |
| `/api/scriptures/` | `scriptures` | Scripture management endpoints |

Each app defines its own `urls.py` with detailed endpoint mappings.

### `wsgi.py`
**Web Server Gateway Interface** entry point. Used by production servers (gunicorn, uWSGI)
to serve the Django application. Exposes the `application` callable.

### `asgi.py`
**Asynchronous Server Gateway Interface** entry point. Used by async servers (daphne, uvicorn)
for WebSocket support if needed in the future. Exposes the `application` callable.

### `__init__.py`
Empty file that makes the `moksha/` directory a Python package.
