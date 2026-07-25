"""
Main Streamlit application for Moksha AI.

This is the frontend that communicates with the Django REST API.
All backend logic (RAG, auth, chat management) lives in Django.
"""

import logging
import os
import sys
import warnings
from pathlib import Path

import streamlit as st

try:
    from streamlit_theme import st_theme
except ImportError:
    st_theme = None

# Add project root to path for Django settings
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Django setup for settings access
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings")
import django  # noqa: E402

django.setup()

from streamlit_ui.api_client import MokshaAPIClient  # noqa: E402

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("streamlit_ui.main")

# UI Configuration
BOT_EMOJI = "🕉️"
USER_EMOJI = "🧘"


def get_colors(theme: str) -> dict:
    """Get color scheme based on theme."""
    if theme == "light":
        return {
            "bot_bg": "#b2f7ef",
            "bot_font": "#4d0810",
            "user_bg": "#7bdff2",
            "user_font": "#4d0810",
        }
    return {
        "bot_bg": "#124336",
        "bot_font": "#E6F9E6",
        "user_bg": "#13233A",
        "user_font": "#E6F7FF",
    }


def inject_css(theme: str = "dark") -> None:
    """Inject custom CSS for the chat UI."""
    st.markdown(
        """
        <style>
        .chat-message {{
            animation: fadeIn 0.3s ease-in;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .thinking-dots span {{
            display: inline-block;
            font-size: 20px;
            animation: bounce 1.4s infinite;
        }}
        .thinking-dots span:nth-child(2) {{ animation-delay: 0.2s; }}
        .thinking-dots span:nth-child(3) {{ animation-delay: 0.4s; }}
        @keyframes bounce {{
            0%, 80%, 100% {{ transform: scale(0); opacity: 0; }}
            40% {{ transform: scale(1); opacity: 1; }}
        }}
        footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_user_message(content: str, colors: dict) -> str:
    """Format user message HTML bubble."""
    import html

    safe = html.escape(content).replace("\n", "<br>")
    return (
        f'<div style="display:flex;justify-content:flex-end;'
        f'margin-bottom:1rem;">'
        f'<div style="background-color:{colors["user_bg"]};'
        f'color:{colors["user_font"]};border-radius:1rem;'
        f"padding:0.75rem 1rem;max-width:80%;"
        f'word-wrap:break-word;">{safe}</div>'
        f'<span style="font-size:24px;margin-left:0.5rem;">'
        f"{USER_EMOJI}</span></div>"
    )


def format_bot_message(content: str, colors: dict) -> str:
    """Format bot message HTML bubble."""
    import html

    safe = html.escape(content).replace("\n", "<br>")
    return (
        f'<div style="display:flex;justify-content:flex-start;'
        f'margin-bottom:1rem;">'
        f'<span style="font-size:24px;margin-right:0.5rem;">'
        f"{BOT_EMOJI}</span>"
        f'<div style="background-color:{colors["bot_bg"]};'
        f'color:{colors["bot_font"]};border-radius:1rem;'
        f"padding:0.75rem 1rem;max-width:80%;"
        f'word-wrap:break-word;">{safe}</div></div>'
    )


def show_thinking_animation(placeholder, colors: dict) -> None:
    """Show thinking animation."""
    html_content = (
        f'<div style="display:flex;align-items:flex-start;'
        f'margin-bottom:1rem;">'
        f'<span style="font-size:24px;margin-right:0.5rem;">'
        f"{BOT_EMOJI}</span>"
        f'<div style="background-color:{colors["bot_bg"]};'
        f'border-radius:1rem;padding:0.75rem 1rem;">'
        f'<div class="thinking-dots">'
        f"<span>●</span><span>●</span><span>●</span>"
        f"</div></div></div>"
    )
    placeholder.markdown(html_content, unsafe_allow_html=True)


def display_complete_response(
    text: str, placeholder, colors: dict, words_per: int = 5
) -> None:
    """Display response with simulated typing effect."""
    words = text.split()
    displayed = ""
    for i in range(0, len(words), words_per):
        batch = words[i : i + words_per]
        displayed += " " + " ".join(batch)
        placeholder.markdown(
            format_bot_message(displayed.strip(), colors),
            unsafe_allow_html=True,
        )
        import time

        time.sleep(0.05)
    placeholder.markdown(format_bot_message(text, colors), unsafe_allow_html=True)


def display_sources(sources: list[dict]) -> None:
    """Render persisted evidence without mixing it into assistant prose."""
    if not sources:
        return
    with st.expander("📚 Sources and passages", expanded=False):
        for source in sources:
            st.markdown(
                f"**{source.get('scripture', 'Scripture')}** — "
                f"{source.get('file_name', 'Unknown volume')}, "
                f"page {source.get('page', 'N/A')} "
                f"(relevance {source.get('score', 0):.2f})"
            )
            st.caption(source.get("excerpt", source.get("text_preview", "")))


# ─── Auth Screens ───────────────────────────────────────────────────────────


def login_screen(client: MokshaAPIClient) -> bool:
    """Render login/register screen. Returns True if authenticated."""
    st.markdown(
        f"<h1 style='text-align:center;'>{BOT_EMOJI} Moksha AI</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#666;'>" "Your Vedic Spiritual Guide</p>",
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button(
                "Login", use_container_width=True, type="primary"
            )
            if submitted:
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    result = client.login(email, password)
                    if result["success"]:
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        error = result.get("error", {})
                        st.error(f"Login failed: {error.get('detail', error)}")

    with tab_register:
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_name = st.text_input("Spiritual Name (optional)", key="reg_name")
            reg_password = st.text_input(
                "Password", type="password", key="reg_password"
            )
            reg_confirm = st.text_input(
                "Confirm Password", type="password", key="reg_confirm"
            )
            submitted = st.form_submit_button(
                "Register", use_container_width=True, type="primary"
            )
            if submitted:
                if not reg_email or not reg_password:
                    st.error("Email and password are required.")
                elif reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    result = client.register(reg_email, reg_password, reg_name)
                    if result["success"]:
                        # Auto-login after registration
                        login_result = client.login(reg_email, reg_password)
                        if login_result["success"]:
                            st.success("Registered and logged in!")
                            st.rerun()
                        else:
                            st.success("Registered! Please login.")
                    else:
                        error = result.get("error", {})
                        st.error(f"Registration failed: {error}")

    return False


# ─── Main Chat Screen ───────────────────────────────────────────────────────


def render_sidebar(
    client: MokshaAPIClient,
) -> str | None:
    """Render sidebar with chat history. Returns selected chat ID."""
    with st.sidebar:
        st.markdown(f"### {BOT_EMOJI} Moksha AI")
        st.markdown("*Your Spiritual Guide*")
        st.divider()

        # Profile
        profile = client.get_profile()
        if profile:
            st.markdown(f"**🙏 {profile.get('spiritual_name', 'Seekers')}**")
            st.caption(profile.get("email", ""))

        if st.button("🚪 Logout", use_container_width=True):
            client.logout()
            st.rerun()

        st.divider()

        # New Chat
        if st.button(
            "➕ New Conversation",
            use_container_width=True,
            type="primary",
        ):
            chat = client.create_chat()
            if chat:
                st.session_state.current_chat_id = chat["id"]
                st.session_state.messages = []
                st.rerun()

        st.divider()
        st.markdown("### 💬 Chat History")

        chats = client.list_chats()
        if not chats:
            st.info("No previous conversations")
        else:
            for chat in chats:
                chat_id = str(chat["id"])
                chat_name = chat.get("name", "Untitled")
                is_current = chat_id == st.session_state.get("current_chat_id")

                if st.button(
                    f"{chat_name}",
                    key=f"chat_{chat_id}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary",
                ):
                    st.session_state.current_chat_id = chat_id
                    full_chat = client.get_chat(chat_id)
                    if full_chat:
                        st.session_state.messages = full_chat.get("messages", [])
                    else:
                        st.session_state.messages = []
                    st.rerun()

        st.divider()

        # Available Scriptures
        with st.expander("📚 Available Scriptures", expanded=False):
            scriptures = client.list_scriptures()
            if scriptures:
                for s in scriptures:
                    st.markdown(f"**📁 {s['name']}**")
                    if s.get("volumes"):
                        for v in s["volumes"]:
                            st.caption(f"  📄 {v['file_name']}")
            else:
                st.info("No scriptures indexed. Run discover_scriptures command.")

        # Settings
        with st.expander("⚙️ Settings", expanded=False):
            st.markdown("#### Danger Zone")
            if st.button(
                "🗑️ Clear All Chats",
                use_container_width=True,
                key="clear_all_btn",
            ):
                st.session_state["confirm_clear"] = True

            if st.session_state.get("confirm_clear"):
                st.warning("⚠️ This will delete ALL chat history!")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Confirm", key="confirm_clear_btn"):
                        chats = client.list_chats()
                        for chat in chats:
                            client.delete_chat(str(chat["id"]))
                        st.session_state.pop("confirm_clear", None)
                        # Create new chat
                        new_chat = client.create_chat()
                        if new_chat:
                            st.session_state.current_chat_id = new_chat["id"]
                            st.session_state.messages = []
                        st.rerun()
                with c2:
                    if st.button("Cancel", key="cancel_clear_btn"):
                        st.session_state.pop("confirm_clear", None)
                        st.rerun()

    current_chat_id = st.session_state.get("current_chat_id")
    return str(current_chat_id) if current_chat_id is not None else None


def render_chat(
    client: MokshaAPIClient,
    chat_id: str,
    colors: dict,
) -> None:
    """Render the main chat area."""
    # Header
    col1, col2 = st.columns([1, 5])
    with col1:
        st.markdown(
            f"<h1 style='font-size:3rem;'>{BOT_EMOJI}</h1>",
            unsafe_allow_html=True,
        )
    with col2:
        st.title("Moksha AI")
        st.caption("Your Vedic Spiritual Guide")

    messages = st.session_state.get("messages", [])

    if not messages:
        st.markdown(
            """
        <div style="text-align:center;padding:2rem;color:#666;">
            <div style="text-align:left;max-width:600px;margin:0 auto;">
                <p><strong>You can ask about:</strong></p>
                <ul style="list-style-type:none;padding-left:0;">
                    <li>🙏 Life's purpose and dharma</li>
                    <li>⚖️ Righteousness and moral dilemmas</li>
                    <li>🔄 Karma and its effects</li>
                    <li>🧘 Meditation and spiritual practices</li>
                    <li>📚 Scripture teachings and interpretations</li>
                    <li>💭 General spiritual guidance</li>
                </ul>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        for msg in messages:
            if msg.get("role") == "user":
                st.markdown(
                    format_user_message(msg.get("content", ""), colors),
                    unsafe_allow_html=True,
                )
            elif msg.get("role") == "assistant":
                st.markdown(
                    format_bot_message(msg.get("content", ""), colors),
                    unsafe_allow_html=True,
                )
                display_sources(msg.get("sources", []))

    # Handle queued response
    if st.session_state.get("awaiting_response"):
        _generate_response(client, chat_id, colors)

    # Chat input
    user_input = st.chat_input(
        placeholder="Ask your spiritual question...",
        disabled=st.session_state.get("awaiting_response", False),
    )

    if user_input and not st.session_state.get("awaiting_response"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state["awaiting_response"] = True
        st.rerun()


def _generate_response(
    client: MokshaAPIClient,
    chat_id: str,
    colors: dict,
) -> None:
    """Generate AI response via API."""
    messages = st.session_state.get("messages", [])
    if not messages:
        st.session_state["awaiting_response"] = False
        return

    last_query = messages[-1].get("content", "")
    response_placeholder = st.empty()
    show_thinking_animation(response_placeholder, colors)

    try:
        result = client.query(chat_id, last_query)

        if result["success"]:
            data = result["data"]
            full_response = data.get("response", "")
            sources = data.get("sources", [])

            display_complete_response(full_response, response_placeholder, colors)

            st.session_state.messages.append(
                {"role": "assistant", "content": full_response, "sources": sources}
            )
            display_sources(sources)
        else:
            error_msg = f"⚠️ Error: {result.get('error', 'Unknown error')}"
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )
            response_placeholder.markdown(
                format_bot_message(error_msg, colors),
                unsafe_allow_html=True,
            )

    except Exception as e:
        logger.exception(f"Error generating response: {e}")
        error_msg = f"⚠️ An error occurred: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        response_placeholder.markdown(
            format_bot_message(error_msg, colors),
            unsafe_allow_html=True,
        )

    finally:
        st.session_state["awaiting_response"] = False
        st.rerun()


# ─── Main Entry Point ───────────────────────────────────────────────────────


def main() -> None:
    """Main entry point for the Streamlit app."""
    st.set_page_config(
        page_title="Moksha AI - Spiritual Guide",
        layout="centered",
        page_icon=BOT_EMOJI,
        initial_sidebar_state="expanded",
    )

    # Theme
    if st_theme is not None:
        try:
            theme_dict = st_theme()
            theme = (
                theme_dict.get("base", "dark")
                if isinstance(theme_dict, dict)
                else "dark"
            )
        except Exception:
            theme = "dark"
    else:
        theme = "dark"
    colors = get_colors(theme)
    inject_css(theme)

    # API Client
    client = MokshaAPIClient()

    # Check if authenticated
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = ""
    if "refresh_token" not in st.session_state:
        st.session_state["refresh_token"] = ""

    if not client.is_authenticated():
        login_screen(client)
        return

    # Initialize chat
    if "current_chat_id" not in st.session_state:
        chats = client.list_chats()
        if chats:
            last_chat = chats[0]
            st.session_state.current_chat_id = str(last_chat["id"])
            full_chat = client.get_chat(str(last_chat["id"]))
            st.session_state.messages = (
                full_chat.get("messages", []) if full_chat else []
            )
        else:
            new_chat = client.create_chat()
            if new_chat:
                st.session_state.current_chat_id = new_chat["id"]
                st.session_state.messages = []

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "awaiting_response" not in st.session_state:
        st.session_state.awaiting_response = False

    # Render sidebar
    selected = render_sidebar(client)
    if selected and selected != st.session_state.get("current_chat_id"):
        st.session_state.current_chat_id = selected
        full_chat = client.get_chat(selected)
        st.session_state.messages = full_chat.get("messages", []) if full_chat else []
        st.session_state.awaiting_response = False
        st.rerun()

    # Render chat
    current_id = st.session_state.get("current_chat_id")
    if current_id:
        render_chat(client, current_id, colors)


if __name__ == "__main__":
    main()
