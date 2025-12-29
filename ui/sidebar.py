"""
Sidebar with chat history and scripture info
"""

from typing import Optional

import streamlit as st

from core.chat_manager import ChatManager
from core.document_loader import ScriptureDocumentLoader


class Sidebar:
    """Sidebar component for chat history"""

    def __init__(
        self, chat_manager: ChatManager, doc_loader: ScriptureDocumentLoader = None
    ):
        self.chat_manager = chat_manager
        self.doc_loader = doc_loader

    def render(self, current_chat_id: Optional[str] = None) -> Optional[str]:
        """
        Render sidebar with chat history
        Returns: Selected chat ID or None for new chat
        """

        with st.sidebar:
            # Logo/Header
            st.markdown("### 🕉️ Moksha AI")
            st.markdown("*Your Spiritual Guide*")

            # Available Scriptures Section
            if self.doc_loader:
                with st.expander("📚 Available Scriptures", expanded=False):
                    scripture_summary = self.doc_loader.get_scripture_summary()

                    if scripture_summary:
                        for scripture, count in scripture_summary.items():
                            st.markdown(f"**{scripture}**: {count} file(s)")

                    else:
                        st.info("No scriptures loaded. Add PDFs to data/docs/")

            # Chat History Section
            st.markdown("### 💬 Chat History")

            # New Chat Button
            if st.button(
                "➕ New Conversation", use_container_width=True, type="primary"
            ):
                new_id = self.chat_manager.create_new_chat()
                st.session_state.current_chat_id = new_id
                st.session_state.messages = []
                st.rerun()

            chats = self.chat_manager.get_all_chats()

            if not chats:
                st.info("No previous conversations")

                return current_chat_id

            # Display chats with better alignment
            selected_chat = None

            for chat in chats:
                chat_id = chat["id"]
                chat_name = chat["name"]
                message_count = chat.get("message_count", 0)

                # Chat item with actions
                is_current = chat_id == current_chat_id

                # Create a container for the chat item
                chat_container = st.container()

                with chat_container:
                    # Main chat button
                    button_label = f"{'📌 ' if is_current else '💬 '}{chat_name}"

                    if st.button(
                        button_label,
                        key=f"chat_{chat_id}",
                        use_container_width=True,
                        type="primary" if is_current else "secondary",
                    ):
                        selected_chat = chat_id

                    # Action buttons row
                    col1, col2, col3 = st.columns([6, 1, 1])

                    with col2:
                        if st.button(
                            "✏️",
                            key=f"rename_{chat_id}",
                            help="Rename",
                            use_container_width=True,
                        ):
                            st.session_state[f"renaming_{chat_id}"] = True
                            st.rerun()

                    with col3:
                        if st.button(
                            "🗑️",
                            key=f"delete_{chat_id}",
                            help="Delete",
                            use_container_width=True,
                        ):
                            if self.chat_manager.delete_chat(chat_id):
                                # If deleted chat was current, create new one
                                if chat_id == current_chat_id:
                                    new_id = self.chat_manager.create_new_chat()
                                    st.session_state.current_chat_id = new_id
                                    st.session_state.messages = []

                                st.rerun()

                    # Rename dialog
                    if st.session_state.get(f"renaming_{chat_id}", False):
                        new_name = st.text_input(
                            "New name:", value=chat_name, key=f"new_name_{chat_id}"
                        )

                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button(
                                "✅ Save",
                                key=f"save_{chat_id}",
                                use_container_width=True,
                            ):
                                self.chat_manager.rename_chat(chat_id, new_name)
                                st.session_state[f"renaming_{chat_id}"] = False
                                st.rerun()

                        with col_b:
                            if st.button(
                                "❌ Cancel",
                                key=f"cancel_{chat_id}",
                                use_container_width=True,
                            ):
                                st.session_state[f"renaming_{chat_id}"] = False
                                st.rerun()

                    # Show message count
                    if message_count > 0:
                        st.caption(f"  {message_count} messages")

                    st.divider()  # Separator between chats

            # Info section
            with st.expander("ℹ️ About", expanded=False):
                st.markdown(
                    """
                **Moksha AI** is your spiritual companion, 
                grounded in Vedic wisdom and sacred scriptures.
                
                **Features:**
                - 📖 Scripture-based answers
                - 🔍 Page-level citations
                - 🧠 Intelligent query routing
                - 💬 Continuous conversations
                
                **Ask about:**
                - Life's purpose and dharma
                - Karma and spiritual practices
                - Scripture teachings and meanings
                - Meditation and self-realization
                
                All answers are based on authentic texts.
                """
                )

            # Settings/Debug
            with st.expander("⚙️ Settings", expanded=False):
                st.markdown("#### Danger Zone")

                if st.button(
                    "🗑️ Clear All Chats", type="secondary", use_container_width=True
                ):
                    st.warning("This will delete ALL chat history!")

                    col_confirm, col_cancel = st.columns(2)

                    with col_confirm:
                        if st.button(
                            "⚠️ Confirm",
                            key="confirm_delete_all",
                            use_container_width=True,
                        ):
                            count = self.chat_manager.clear_all_chats()
                            st.success(f"Cleared {count} chats")
                            new_id = self.chat_manager.create_new_chat()
                            st.session_state.current_chat_id = new_id
                            st.session_state.messages = []
                            st.rerun()

                    with col_cancel:
                        if st.button(
                            "Cancel", key="cancel_delete_all", use_container_width=True
                        ):
                            st.rerun()

            return selected_chat
