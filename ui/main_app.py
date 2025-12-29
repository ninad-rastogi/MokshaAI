"""
Main Streamlit application with proper caching and immediate message display
"""

import logging
import time
import warnings

import streamlit as st
from streamlit_theme import st_theme

# Import core modules
from core.chat_manager import ChatManager
from core.config import (
    BOT_EMOJI,
    CHATS_DIR,
    CHUNK_SIZE,
    DOCS_DIR,
    EMBEDDINGS_DIR,
    MAX_CHAT_NAME_LENGTH,
    META_FILE,
    OLLAMA_MODEL,
    OLLAMA_SERVER,
    RESPONSE_CHUNK_SIZE,
    SENTENCE_TRANSFORMERS_MODEL,
    USER_EMOJI,
    VEDIC_SYSTEM_PROMPT,
)
from core.document_loader import ScriptureDocumentLoader
from core.embeddings import EmbeddingsManager
from core.rag_engine import RAGEngine

# Import UI modules
from ui.chat_display import ChatDisplay
from ui.sidebar import Sidebar
from ui.styles import get_theme_colors, inject_custom_css

# Suppress warnings
warnings.filterwarnings("ignore")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("moksha_ai.main")


class MokshaAIApp:
    """Main application class"""

    def __init__(self):
        self.setup_page_config()
        self.setup_theme()
        self.initialize_session_state()
        self.initialize_components()

    def setup_page_config(self):
        """Configure Streamlit page"""

        st.set_page_config(
            page_title="Moksha AI - Spiritual Guide",
            layout="centered",
            page_icon="🕉️",
            initial_sidebar_state="expanded",
        )

    def setup_theme(self):
        """Setup theme and styling"""

        theme_dict = st_theme()
        self.theme = (
            theme_dict.get("base", "dark") if isinstance(theme_dict, dict) else "dark"
        )

        self.colors = get_theme_colors(self.theme)

        # Inject custom CSS (with settings menu enabled)
        inject_custom_css()

        # Set logo (REVERSED: dark logo for light theme, light logo for dark theme)
        logo_path = (
            "./images/MokshaAI_dark_cropped.png"
            if self.theme == "light"
            else "./images/MokshaAI_light_cropped.png"
        )

        self.logo_path = logo_path

        try:
            st.logo(image=logo_path, size="large")

        except Exception as e:
            pass

    @st.cache_resource(
        show_spinner=False
    )  # No TTL - cache until restart or metadata changes
    def initialize_components(_self):
        """Initialize core components - only reload if documents change"""
        logger.info("Initializing Moksha AI components...")

        # 1. Document Loader
        doc_loader = ScriptureDocumentLoader(DOCS_DIR)

        # 2. Load documents with metadata
        documents = doc_loader.load_documents_with_metadata()

        available_scriptures = doc_loader.get_available_scriptures()

        # 3. Embeddings Manager
        embeddings_manager = EmbeddingsManager(
            embeddings_dir=EMBEDDINGS_DIR,
            meta_file=META_FILE,
            embed_model_name=SENTENCE_TRANSFORMERS_MODEL,
            ollama_model=OLLAMA_MODEL,
            ollama_server=OLLAMA_SERVER,
        )

        # 4. Build/load index (automatically checks metadata for changes)
        index = embeddings_manager.build_index(documents, DOCS_DIR)

        # 5. RAG Engine with intelligent routing
        rag_engine = RAGEngine(
            index=index,
            ollama_model=OLLAMA_MODEL,
            ollama_server=OLLAMA_SERVER,
            system_prompt=VEDIC_SYSTEM_PROMPT,
            available_scriptures=available_scriptures,
        )

        logger.info("Components initialized successfully")

        return {
            "doc_loader": doc_loader,
            "rag_engine": rag_engine,
            "has_docs": len(documents) > 0,
        }

    def initialize_session_state(self):
        """Initialize session state variables"""

        chat_manager = ChatManager(
            chats_dir=CHATS_DIR,
            ollama_model=OLLAMA_MODEL,
            ollama_server=OLLAMA_SERVER,
            max_name_length=MAX_CHAT_NAME_LENGTH,
        )

        if "current_chat_id" not in st.session_state:
            # Load last chat or create new one
            all_chats = chat_manager.get_all_chats()

            if all_chats:
                last_chat = all_chats[0]
                st.session_state.current_chat_id = last_chat["id"]
                st.session_state.messages = chat_manager.get_messages(last_chat["id"])
                logger.info(f"Loaded last chat: {last_chat['name']}")

            else:
                st.session_state.current_chat_id = chat_manager.create_new_chat()
                st.session_state.messages = []

        if "messages" not in st.session_state:
            st.session_state.messages = []

        if "awaiting_response" not in st.session_state:
            st.session_state.awaiting_response = False

        if "user_message_displayed" not in st.session_state:
            st.session_state.user_message_displayed = False

    def run(self):
        """Main application loop"""
        # Header with logo
        col1, col2 = st.columns([1, 5])

        with col1:
            try:
                st.image(self.logo_path, width=80)

            except Exception as e:
                st.markdown(
                    f"<h1 style='font-size: 3rem;'>{BOT_EMOJI}</h1>",
                    unsafe_allow_html=True,
                )

        with col2:
            st.title("Moksha AI")
            st.caption("Your Vedic Spiritual Guide")

        # Initialize components (cached - only reloads if metadata changes)
        components = self.initialize_components()
        rag_engine = components["rag_engine"]
        doc_loader = components["doc_loader"]
        has_docs = components["has_docs"]

        # Chat Manager
        chat_manager = ChatManager(
            chats_dir=CHATS_DIR,
            ollama_model=OLLAMA_MODEL,
            ollama_server=OLLAMA_SERVER,
            max_name_length=MAX_CHAT_NAME_LENGTH,
        )

        # Sidebar
        sidebar = Sidebar(chat_manager, doc_loader)
        selected_chat = sidebar.render(st.session_state.current_chat_id)

        # Handle chat selection
        if selected_chat and selected_chat != st.session_state.current_chat_id:
            st.session_state.current_chat_id = selected_chat
            st.session_state.messages = chat_manager.get_messages(selected_chat)
            st.session_state.awaiting_response = False
            st.rerun()

        # Chat Display
        chat_display = ChatDisplay(self.colors, BOT_EMOJI, USER_EMOJI)

        # Show welcome or history
        if not st.session_state.messages:
            chat_display.display_welcome_message()

        else:
            chat_display.render_message_history(st.session_state.messages)

        # Handle queued response generation
        if st.session_state.awaiting_response:
            self._generate_response(chat_manager, rag_engine, chat_display, has_docs)

        # Chat input
        user_input = st.chat_input(
            placeholder="Ask your spiritual question...",
            disabled=st.session_state.awaiting_response,
        )

        if user_input:
            self._handle_user_input(user_input, chat_manager, chat_display)

    def _handle_user_input(
        self, user_input: str, chat_manager: ChatManager, chat_display: ChatDisplay
    ):
        """Handle new user input - show message immediately"""
        # Add to messages
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Save to chat file
        chat_manager.add_message(st.session_state.current_chat_id, "user", user_input)

        # Mark that we need to show user message
        st.session_state.user_message_displayed = False

        # Queue response generation
        st.session_state.awaiting_response = True
        st.rerun()

    def _generate_response(
        self,
        chat_manager: ChatManager,
        rag_engine: RAGEngine,
        chat_display: ChatDisplay,
        has_docs: bool,
    ):
        """Generate bot response with intelligent routing using .invoke()"""

        last_query = st.session_state.messages[-1]["content"]
        response_placeholder = chat_display.create_message_placeholder()

        # Show thinking animation
        chat_display.show_thinking_animation(response_placeholder)

        try:
            # Route query intelligently
            route, requires_scripture = rag_engine.route_query(last_query)

            logger.info(
                f"Query route: {route}, requires_scripture: {requires_scripture}"
            )

            if route == "rag" and has_docs:
                # Use RAG with custom implementation
                full_response, sources = rag_engine.query_with_rag(
                    query=last_query,
                    session_id=st.session_state.current_chat_id,
                    messages_history=st.session_state.messages[:-1],
                )

                # Display response with typing effect
                chat_display.display_complete_response(
                    full_response, response_placeholder
                )

                # Display sources
                if sources:
                    chat_display.display_sources(sources)

            else:
                # Use general conversation mode
                full_response = rag_engine.query_without_rag(
                    query=last_query, messages_history=st.session_state.messages[:-1]
                )

                # Display response with typing effect
                chat_display.display_complete_response(
                    full_response, response_placeholder
                )

            # Add to session state
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

            # Save to chat file
            chat_manager.add_message(
                st.session_state.current_chat_id,
                "assistant",
                full_response,
                mode=route.upper(),
            )

        except Exception as e:
            logger.exception(f"Error generating response: {e}")

            error_msg = f"⚠️ An error occurred: {str(e)}\n\nPlease try again or rephrase your question."

            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )

            chat_manager.add_message(
                st.session_state.current_chat_id, "assistant", error_msg, mode="ERROR"
            )

            # Display error
            response_placeholder.markdown(
                chat_display._format_bot_message(error_msg), unsafe_allow_html=True
            )

        finally:
            # Clear awaiting flag and rerun
            st.session_state.awaiting_response = False
            time.sleep(0.5)
            st.rerun()


def main():
    """Entry point"""

    app = MokshaAIApp()
    app.run()


if __name__ == "__main__":
    main()
