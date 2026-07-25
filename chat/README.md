# chat/ — Chat Sessions & RAG Engine App

This is the **core Django app** that handles chat sessions, message persistence, and the
Retrieval-Augmented Generation (RAG) engine. It replaces the old `core/` package and
`core/chat_manager.py`.

## Purpose

The chat app provides:
- **Chat CRUD**: Create, read, rename, delete chat sessions
- **Message persistence**: Store all messages in PostgreSQL (replaces old JSON files)
- **Query endpoint**: The main `/api/chat/<id>/query/` endpoint that processes user questions
- **RAG engine**: Intelligent query routing + scripture-based answering
- **Management commands**: `discover_scriptures` and `migrate_json_chats`

## Files

### `models.py` — Chat & Message Models

**`Chat` model:**
- `id`: UUID primary key (auto-generated)
- `user`: ForeignKey to `users.User` (each chat belongs to one user)
- `name`: Chat title (max 50 chars, defaults to "New Spiritual Conversation")
- `created_at` / `updated_at`: Auto timestamps
- Ordered by `-updated_at` (most recent first)

**`Message` model:**
- `chat`: ForeignKey to `Chat` (each message belongs to one chat)
- `role`: Either "user" or "assistant"
- `content`: The message text
- `mode`: "RAG", "GENERAL", or "ERROR" — how the response was generated
- `created_at`: Auto timestamp
- Ordered by `created_at` (chronological)

### `serializers.py` — DRF Serializers

- **`MessageSerializer`**: Serializes Message model (id, role, content, mode, created_at)
- **`ChatSerializer`**: Serializes Chat with `message_count` annotation
- **`ChatDetailSerializer`**: Serializes Chat with full nested messages list
- **`QuerySerializer`**: Validates query requests (message field, max 5000 chars)
- **`QueryResponseSerializer`**: Validates response format (response, sources, mode)

### `views.py` — ChatViewSet

A Django REST Framework `ViewSet` (not ModelViewSet — custom logic):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `list` | `GET /api/chat/` | List all chats for current user |
| `create` | `POST /api/chat/` | Create new chat |
| `retrieve` | `GET /api/chat/<id>/` | Get chat with all messages |
| `destroy` | `DELETE /api/chat/<id>/` | Delete chat |
| `rename` | `PATCH /api/chat/<id>/rename/` | Rename chat |
| `query` | `POST /api/chat/<id>/query/` | Submit question, get AI response |
| `discover` | `POST /api/chat/discover/` | Trigger scripture discovery |

**The `query` action** is the main endpoint:
1. Saves the user's message to the database
2. Calls the RAG engine (currently a placeholder — full integration in `chat/rag/engine.py`)
3. Saves the assistant's response
4. Auto-names the chat after 4+ messages
5. Returns `{response, sources, mode}`

### `urls.py`
Uses DRF's `DefaultRouter` to auto-generate standard CRUD routes from the ViewSet.

### `admin.py`
- `ChatAdmin`: Shows chats with inline messages, searchable by name/email
- `MessageAdmin`: Shows messages filterable by role/mode/date

### `apps.py`
Django app configuration. Sets `verbose_name = "Chat & Conversations"`.

## Subdirectories

### `rag/` — RAG Engine
See [chat/rag/README.md](rag/README.md) for detailed documentation of:
- `engine.py` — Query routing + RAG pipeline
- `embeddings.py` — PgVector store (replaces ChromaDB)
- `loader.py` — PDF loading with auto-discovery
- `chunker.py` — Semantic chunking for shloka/translation/narration

### `management/commands/` — Management Commands
- `discover_scriptures.py` — Auto-discover and index scripture PDFs
- `migrate_json_chats.py` — One-time migration from JSON files to PostgreSQL

### `tests/` — Tests
- `test_models.py` — Chat and Message model tests
- `test_views.py` — API endpoint tests (not yet created)
- `test_rag.py` — RAG engine tests (not yet created)
