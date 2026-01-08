"""
Sidebar with hover-based 3-dot menu
"""

from typing import Optional

import streamlit as st

from core.chat_manager import ChatManager
from core.document_loader import ScriptureDocumentLoader


class Sidebar:
    """Sidebar component for chat history with hover menu"""

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
            st.divider()

            # New Chat Button
            if st.button(
                "➕ New Conversation", use_container_width=True, type="primary"
            ):
                new_id = self.chat_manager.create_new_chat()
                st.session_state.current_chat_id = new_id
                st.session_state.messages = []
                st.rerun()

            st.divider()

            # Available Scriptures Section
            if self.doc_loader:
                with st.expander("📚 Available Scriptures", expanded=False):
                    scripture_summary = self.doc_loader.get_scripture_summary()

                    if scripture_summary:
                        for scripture, count in scripture_summary.items():
                            st.markdown(f"**{scripture}**: {count} file(s)")

                    else:
                        st.info("No scriptures loaded. Add PDFs to data/docs/")

                st.divider()

            # Chat History Section
            st.markdown("### 💬 Chat History")

            chats = self.chat_manager.get_all_chats()

            if not chats:
                st.info("No previous conversations")
                return current_chat_id

            # Display chats with hover menu
            selected_chat = None

            for chat in chats:
                chat_id = chat["id"]
                chat_name = chat["name"]
                is_current = chat_id == current_chat_id

                # Create chat item with hover menu using HTML
                chat_item_html = f"""
                <div class="chat-item-container">
                    <div class="chat-button-wrapper">
                        <button class="chat-main-button {'current-chat' if is_current else ''}" 
                                data-chat-id="{chat_id}" 
                                title="{chat_name}">
                            {'📌' if is_current else '💬'} {chat_name}
                        </button>
                        <div class="three-dot-menu">
                            <div class="three-dots">⋮</div>
                            <div class="hover-menu">
                                <button class="menu-action rename-action" data-chat-id="{chat_id}" data-action="rename">✏️ Rename</button>
                                <button class="menu-action delete-action" data-chat-id="{chat_id}" data-action="delete">🗑️ Delete</button>
                            </div>
                        </div>
                    </div>
                </div>
                """

                # Render HTML
                st.markdown(chat_item_html, unsafe_allow_html=True)

                # Hidden Streamlit buttons for actual functionality (no label_visibility)
                col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

                # Use markdown to hide button text instead
                with col1:
                    if st.button(
                        "​",  # Zero-width space character
                        key=f"sel_{chat_id}",
                        use_container_width=True,
                    ):
                        selected_chat = chat_id

                with col2:
                    if st.button(
                        "​",
                        key=f"menu_{chat_id}",
                        use_container_width=True,
                    ):
                        pass  # Menu opens on hover via CSS

                with col3:
                    if st.button(
                        "​",
                        key=f"ren_{chat_id}",
                        use_container_width=True,
                        help="Rename",
                    ):
                        st.session_state[f"renaming_{chat_id}"] = True
                        st.rerun()

                with col4:
                    if st.button(
                        "​",
                        key=f"del_{chat_id}",
                        use_container_width=True,
                        help="Delete",
                    ):
                        st.session_state[f"confirm_delete_{chat_id}"] = True
                        st.rerun()

                # Rename dialog
                if st.session_state.get(f"renaming_{chat_id}", False):
                    with st.container():
                        new_name = st.text_input(
                            "New name:",
                            value=chat_name,
                            key=f"new_name_{chat_id}",
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
                                key=f"cancel_rename_{chat_id}",
                                use_container_width=True,
                            ):
                                st.session_state[f"renaming_{chat_id}"] = False
                                st.rerun()

                # Delete confirmation
                if st.session_state.get(f"confirm_delete_{chat_id}", False):
                    with st.container():
                        st.warning("⚠️ Delete this chat?")
                        col_y, col_n = st.columns(2)

                        with col_y:
                            if st.button(
                                "Yes",
                                key=f"yes_delete_{chat_id}",
                                use_container_width=True,
                            ):
                                if self.chat_manager.delete_chat(chat_id):
                                    if chat_id == current_chat_id:
                                        new_id = self.chat_manager.create_new_chat()
                                        st.session_state.current_chat_id = new_id
                                        st.session_state.messages = []
                                st.session_state[f"confirm_delete_{chat_id}"] = False
                                st.rerun()

                        with col_n:
                            if st.button(
                                "No",
                                key=f"no_delete_{chat_id}",
                                use_container_width=True,
                            ):
                                st.session_state[f"confirm_delete_{chat_id}"] = False
                                st.rerun()

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

            # Settings
            with st.expander("⚙️ Settings", expanded=False):
                st.markdown("#### Danger Zone")

                if st.button(
                    "🗑️ Clear All Chats", type="secondary", use_container_width=True
                ):
                    st.session_state["confirm_clear_all"] = True
                    st.rerun()

                if st.session_state.get("confirm_clear_all", False):
                    st.warning("⚠️ This will delete ALL chat history!")

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
                            st.session_state["confirm_clear_all"] = False
                            st.rerun()

                    with col_cancel:
                        if st.button(
                            "Cancel", key="cancel_delete_all", use_container_width=True
                        ):
                            st.session_state["confirm_clear_all"] = False
                            st.rerun()

            return selected_chat
