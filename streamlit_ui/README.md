# streamlit_ui/ — Streamlit Frontend

This package contains the **Streamlit-based user interface** for Moksha AI. It is a pure
HTTP client that communicates with the Django REST API. This replaces the old `ui/` directory
which directly imported `core/` modules.

## Purpose

The Streamlit UI provides:
- **Login/Register screen**: JWT-based authentication flow
- **Chat interface**: Message display with typing animation
- **Sidebar**: Chat history, scripture list, settings
- **API client**: HTTP communication with Django backend

## Key Difference from Old Architecture

**Before (v1.0):** Streamlit imported `core/` modules directly:
```python
from core.chat_manager import ChatManager
from core.rag_engine import RAGEngine
```

**After (v2.0):** Streamlit makes HTTP API calls:
```python
from streamlit_ui.api_client import MokshaAPIClient
client = MokshaAPIClient()
result = client.query(chat_id, message)
```

This decoupling means the frontend and backend can be developed, tested, and deployed
independently.

## Files

### `api_client.py` — MokshaAPIClient Class

HTTP client for the Django REST API. Handles:
- **Token management**: Stores JWT access/refresh tokens in `st.session_state`
- **Auto-refresh**: Automatically refreshes expired access tokens
- **Error handling**: Graceful handling of network errors and auth failures

**Key methods:**

| Method | Description |
|--------|-------------|
| `register(email, password, spiritual_name)` | Create new account |
| `login(email, password)` | Authenticate and store JWT |
| `logout()` | Clear stored tokens |
| `get_profile()` | Get current user profile |
| `is_authenticated()` | Check if user has valid tokens |
| `list_chats()` | Get all chats for current user |
| `create_chat()` | Create new chat session |
| `get_chat(chat_id)` | Get chat with messages |
| `delete_chat(chat_id)` | Delete a chat |
| `rename_chat(chat_id, name)` | Rename a chat |
| `query(chat_id, message)` | Submit question, get AI response |
| `list_scriptures()` | List available scriptures |
| `discover_scriptures()` | Trigger scripture discovery |
| `health_check()` | Check if API is reachable |

### `main_app.py` — Main Streamlit Application

The entry point. Contains:

- **`login_screen(client)`**: Renders login/register tabs. Returns True if authenticated.
- **`render_sidebar(client)`**: Renders the sidebar with:
  - User profile display
  - Logout button
  - New chat button
  - Chat history list (clickable)
  - Available scriptures expander
  - Settings with "Clear All Chats" option
- **`render_chat(client, chat_id, colors)`**: Renders the main chat area with:
  - Header with logo
  - Message history display
  - Thinking animation during response generation
  - Typing effect for responses
  - Chat input field
- **`_generate_response(client, chat_id, colors)`**: Handles the response generation flow:
  - Shows thinking animation
  - Calls `client.query()` API
  - Displays response with typing effect
  - Handles errors gracefully
- **`main()`**: Entry point that orchestrates everything:
  - Sets page config
  - Detects theme (light/dark)
  - Injects CSS
  - Checks authentication
  - Renders appropriate screen

### `__init__.py`
Empty file making `streamlit_ui/` a Python package.

## UI Flow

```
User opens browser → http://localhost:8501
  → No token? → Login/Register screen
  → Has token? → Validate with API
    → Valid? → Main chat screen
    → Invalid? → Try refresh token
      → Success? → Main chat screen
      → Failure? → Login/Register screen
```

## Running

```bash
# Make sure Django is running first:
python manage.py runserver

# Then start Streamlit:
streamlit run streamlit_ui/main_app.py
# Or:
make streamlit
```
