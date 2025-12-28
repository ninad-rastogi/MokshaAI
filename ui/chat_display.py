"""
Chat message display and rendering with safe HTML handling
"""

import html
import time
from typing import Dict, List

import streamlit as st


class ChatDisplay:
    """Handle chat message rendering"""

    def __init__(self, colors: dict, bot_emoji: str = "🕉️", user_emoji: str = "🧘"):
        self.colors = colors
        self.bot_emoji = bot_emoji
        self.user_emoji = user_emoji

    def render_message_history(self, messages: List[Dict]):
        """Render all messages in chat history"""
        conversation_html = ""

        for msg in messages:
            if msg["role"] == "user":
                conversation_html += self._format_user_message(msg["content"])
            elif msg["role"] == "assistant":
                conversation_html += self._format_bot_message(msg["content"])

        if conversation_html:
            st.markdown(conversation_html, unsafe_allow_html=True)

    def _escape_and_format(self, content: str) -> str:
        """Escape HTML but preserve line breaks"""
        # Escape HTML entities
        safe_content = html.escape(content)
        # Convert newlines to <br> for display
        safe_content = safe_content.replace("\n", "<br>")
        return safe_content

    def _format_user_message(self, content: str) -> str:
        """Format user message bubble with safe HTML"""
        safe_content = self._escape_and_format(content)

        return f"""
        <div class="chat-message" style="display: flex; align-items: flex-start; margin-bottom: 1rem;">
            <span style="font-size: 24px; margin-right: 0.5rem;">{self.user_emoji}</span>
            <div style="
                color: {self.colors['user_font']};
                background-color: {self.colors['user_bg']};
                border-radius: 1rem;
                padding: 0.75rem 1rem;
                max-width: 80%;
                word-wrap: break-word;
            ">
                {safe_content}
            </div>
        </div>
        """

    def _format_bot_message(self, content: str) -> str:
        """Format bot message bubble with safe HTML"""
        safe_content = self._escape_and_format(content)

        return f"""
        <div class="chat-message" style="display: flex; align-items: flex-start; margin-bottom: 1rem;">
            <span style="font-size: 24px; margin-right: 0.5rem;">{self.bot_emoji}</span>
            <div style="
                color: {self.colors['bot_font']};
                background-color: {self.colors['bot_bg']};
                border-radius: 1rem;
                padding: 0.75rem 1rem;
                max-width: 80%;
                word-wrap: break-word;
            ">
                {safe_content}
            </div>
        </div>
        """

    def create_message_placeholder(self):
        """Create a placeholder for streaming messages"""
        return st.empty()

    def stream_bot_response(
        self, response_gen, placeholder, chunk_size: int = 2048
    ) -> str:
        """
        Stream bot response to placeholder with safe HTML handling
        Returns: Full response text
        """
        full_response = ""

        try:
            for chunk in response_gen:
                # Handle different chunk formats
                if hasattr(chunk, "content"):
                    chunk_text = chunk.content
                elif hasattr(chunk, "response"):
                    chunk_text = chunk.response
                elif isinstance(chunk, str):
                    chunk_text = chunk
                else:
                    chunk_text = str(chunk)

                full_response += chunk_text

                # Update placeholder with formatted message (HTML is escaped in _format_bot_message)
                display_html = self._format_bot_message(full_response)
                placeholder.markdown(display_html, unsafe_allow_html=True)

                # Small delay for smooth streaming
                time.sleep(0.01)

        except Exception as e:
            error_msg = f"\n\n⚠️ Error during response generation: {str(e)}"
            full_response += error_msg
            display_html = self._format_bot_message(full_response)
            placeholder.markdown(display_html, unsafe_allow_html=True)

        return full_response

    def display_sources(self, sources: List[Dict]):
        """Display scripture sources/citations"""
        if not sources:
            return

        st.markdown("---")
        st.markdown("### 📜 Scripture References")

        for idx, source in enumerate(sources, 1):
            scripture = source.get("scripture", "Unknown")
            page = source.get("page", "N/A")
            file_name = source.get("file_name", "Unknown")
            score = source.get("score", 0.0)

            with st.expander(f"📖 {scripture} - Page {page} (Relevance: {score})"):
                st.markdown(f"**File:** {file_name}")

                if "text_preview" in source:
                    st.markdown("**Preview:**")
                    st.markdown(f"_{source['text_preview']}_")

    def show_thinking_animation(self, placeholder):
        """Show thinking animation"""
        thinking_html = f"""
        <div style="display: flex; align-items: flex-start; margin-bottom: 1rem;">
            <span style="font-size: 24px; margin-right: 0.5rem;">{self.bot_emoji}</span>
            <div style="
                color: {self.colors['bot_font']};
                background-color: {self.colors['bot_bg']};
                border-radius: 1rem;
                padding: 0.75rem 1rem;
            ">
                <div class="thinking-dots">
                    <span>●</span>
                    <span>●</span>
                    <span>●</span>
                </div>
            </div>
        </div>
        """
        placeholder.markdown(thinking_html, unsafe_allow_html=True)

    def display_welcome_message(self):
        """Display welcome message for new chat"""
        welcome_html = f"""
        <div style="text-align: center; padding: 2rem; color: #666;">
            <h2 style="margin-bottom: 1rem;">{self.bot_emoji} Welcome to Moksha AI</h2>
            <p style="font-size: 1.1rem; margin-bottom: 2rem;">
                Your spiritual guide rooted in Vedic wisdom
            </p>
            <div style="text-align: left; max-width: 600px; margin: 0 auto;">
                <p><strong>You can ask about:</strong></p>
                <ul style="list-style-type: none; padding-left: 0;">
                    <li>🙏 Life's purpose and dharma</li>
                    <li>⚖️ Righteousness and moral dilemmas</li>
                    <li>🔄 Karma and its effects</li>
                    <li>🧘 Meditation and spiritual practices</li>
                    <li>📚 Scripture teachings and interpretations</li>
                    <li>💭 General spiritual guidance</li>
                </ul>
                <p style="margin-top: 1rem; font-size: 0.9rem; font-style: italic;">
                    Note: I intelligently determine whether to search scriptures or provide general guidance based on your question.
                </p>
            </div>
        </div>
        """
        st.markdown(welcome_html, unsafe_allow_html=True)
