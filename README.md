# 🕉️ Moksha AI — Vedic Spiritual Guide

A sophisticated AI-powered chatbot that serves as your spiritual companion, deeply rooted in
Hindu Vedic wisdom and sacred scriptures. Moksha AI provides meaningful spiritual conversations,
quotes authentic shlokas with Sanskrit text and Hindi translations, and answers questions based
strictly on sacred texts stored in its knowledge base.

## ✨ Features

- **📚 Scripture-Based RAG**: Answers grounded in authentic Vedic texts using
  Retrieval-Augmented Generation
- **🔍 Page-Level Citations**: Precise references with scripture name, page number, and text
  previews
- **👤 User Authentication**: JWT-based registration and login system
- **💬 Smart Chat Management**: Sidebar with chat history, rename, delete, and auto-naming
- **🌍 Multilingual Embeddings**: Uses `BAAI/bge-m3` model optimized for mixed
  Sanskrit/Hindi/English content
- **📖 Scripture Auto-Discovery**: Automatically detects and indexes PDF scriptures from
  organized folders
- **🎯 Intelligent Query Routing**: LLM classifies queries into Scripture, Guidance, or Casual
  categories
- **📊 Django Admin Panel**: Manage users, scriptures, chat logs, and volumes from a web
  interface
- **🐳 Docker-Ready**: Compose setup for Django + PostgreSQL/PgVector + Streamlit

## 🏗️ Architecture

```
┌──────────────────┐      HTTP/REST       ┌──────────────────┐
│   Streamlit UI    │ ◄──────────────────► │  Django + DRF     │
│   (Frontend)      │    JWT Bearer Tokens │  (Backend + API)  │
└──────────────────┘                       └────────┬─────────┘
                                                    │
                         ┌─────────────────────────┼──────────────────┐
                         ▼                         ▼                  ▼
                  ┌──────────────┐          ┌──────────────┐   ┌────────────┐
                  │  PostgreSQL   │          │   PgVector   │   │   Ollama   │
                  │  (users,      │          │  (embeddings │   │  (LLM:     │
                  │   chats,      │          │   stored as   │   │  llama3)   │
                  │   messages,   │          │   vectors in  │   │            │
                  │   metadata)   │          │   PostgreSQL) │   │            │
                  └──────────────┘          └──────────────┘   └────────────┘
```

**Key Design Decisions:**
- **Django** handles authentication, ORM, admin panel, and REST API (via DRF)
- **PgVector** (PostgreSQL extension) replaces ChromaDB — single database for all data
- **BAAI/bge-m3** embedding model handles mixed Sanskrit/Hindi/English content better than
  the old distiluse model
- **Semantic chunking** splits PDF pages into shloka, translation, and narration chunks
- **Streamlit** is a pure HTTP client — it calls Django REST API for all operations

## 🚀 Quick Start

### Prerequisites

1. **Python 3.14.6** managed by uv (virtual environment at `D:\Ninad\Python\.env`)
2. **PostgreSQL 16+** with PgVector extension
3. **Ollama** installed and running locally
   ```bash
   ollama list
   # The default local model is imported as:
   # moksha-qwen3:4b-instruct-q3km
   ```

### Setup Steps

1. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your PostgreSQL credentials
   ```

2. **Create the database:**
   ```bash
   createdb moksha
   psql moksha -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

3. **Install dependencies with uv:**
   ```bash
   # PowerShell
   $env:UV_PROJECT_ENVIRONMENT = "D:\Ninad\Python\.env"
   uv sync --locked --extra dev --python 3.14.6
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Add scripture PDFs:**
   ```
   data/docs/
   └── Mahabharata/
       ├── Mahabharata Volume 1.pdf
       ├── Mahabharata Volume 2.pdf
       └── ... (Volumes 3-6)
   ```

6. **Index scriptures:**
   ```bash
   python manage.py discover_scriptures
   ```

7. **Start Django backend:**
   ```bash
   python manage.py runserver
   ```

8. **Start Streamlit frontend (new terminal):**
   ```bash
   streamlit run streamlit_ui/main_app.py
   ```

9. **Open browser:** Navigate to `http://localhost:8501`

## 📁 Project Structure & Documentation

Each major folder has a detailed README explaining its contents:

| Folder | README | Description |
|--------|--------|-------------|
| `moksha/` | [moksha/README.md](moksha/README.md) | Django project settings, URL routing, WSGI/ASGI config |
| `users/` | [users/README.md](users/README.md) | Custom User model, JWT auth, registration/login API |
| `chat/` | [chat/README.md](chat/README.md) | Chat/Message models, API views, RAG engine, management commands |
| `scriptures/` | [scriptures/README.md](scriptures/README.md) | Scripture/Volume models, auto-discovery, admin |
| `chat/rag/` | [chat/rag/README.md](chat/rag/README.md) | RAG engine, PgVector store, PDF loader, semantic chunker |
| `streamlit_ui/` | [streamlit_ui/README.md](streamlit_ui/README.md) | Streamlit frontend, API client, UI components |
| `tests/` | [tests/README.md](tests/README.md) | Test structure, fixtures, integration tests |
| `docs/` | [docs/README.md](docs/README.md) | Architecture, API reference, deployment guides |

## 🎯 Usage Examples

### API Endpoints

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/auth/register/` | POST | Create new account | No |
| `/api/auth/login/` | POST | Get JWT tokens | No |
| `/api/auth/refresh/` | POST | Refresh JWT token | No |
| `/api/auth/me/` | GET/PUT | Get/update profile | Yes |
| `/api/auth/health/` | GET | Health check | No |
| `/api/chat/` | GET | List user's chats | Yes |
| `/api/chat/` | POST | Create new chat | Yes |
| `/api/chat/<id>/` | GET | Get chat with messages | Yes |
| `/api/chat/<id>/` | DELETE | Delete chat | Yes |
| `/api/chat/<id>/query/` | POST | Submit query, get AI response | Yes |
| `/api/chat/<id>/rename/` | PATCH | Rename chat | Yes |
| `/api/scriptures/` | GET | List scriptures | Yes |
| `/api/scriptures/<id>/` | GET | Scripture details | Yes |
| `/api/scriptures/<id>/reindex/` | POST | Trigger re-indexing | Yes |

### Example Questions

- "What does the Mahabharata say about dharma?"
- "How can I find inner peace according to Vedic wisdom?"
- "Quote a shloka about karma from the scriptures"
- "What is the purpose of meditation?"

## ⚙️ Key Configuration

| Setting | Default | Location |
|---------|---------|----------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | `.env` |
| `OLLAMA_MODEL` | `moksha-qwen3:4b-instruct-q3km` | `.env` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | `.env` |
| `EMBEDDING_DEVICE` | `cpu` | `.env` |
| `POSTGRES_DB` | `moksha` | `.env` |
| `DJANGO_SECRET_KEY` | (generated) | `.env` |
| `DJANGO_API_URL` | `http://localhost:8000` | `.env` |

## 🔧 Code Quality

```bash
make format        # Format code with black
make lint          # Run flake8 and black --check
make test          # Run pytest with coverage
make help          # Show all available commands
```

## 🧪 Testing

```bash
pytest                              # All tests
pytest --cov=. --cov-report=html    # With coverage report
pytest -x                           # Stop on first failure
pytest users/tests/                 # Users app tests only
pytest chat/tests/                  # Chat app tests only
```

## 🐳 Docker Deployment

```bash
docker-compose up --build    # Start all services
docker-compose up db         # Start only PostgreSQL
docker-compose up django     # Start only Django
docker-compose up streamlit  # Start only Streamlit
```

## 📝 Development Workflow

1. **Model changes:** Edit `models.py` → `python manage.py makemigrations` → `python manage.py migrate`
2. **New management command:** Add to `management/commands/` → `python manage.py <command>`
3. **New API endpoint:** Add to `views.py` + `urls.py` → test via DRF browsable API at `http://localhost:8000/api/`
4. **Re-index scriptures:** Add PDFs to `data/docs/<ScriptureName>/` → `python manage.py discover_scriptures`

## 📄 License

MIT License. Please respect the sacred nature of the scriptures and use this tool with reverence.

## 🙏 Acknowledgments

- Built with Django, Django REST Framework, Streamlit, LlamaIndex, and LangChain
- Powered by Ollama for local LLM inference
- Inspired by the timeless wisdom of Vedic texts

---

**May this tool serve your spiritual journey. Om Shanti. 🕉️**
