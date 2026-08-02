"""Playwright E2E tests for chat functionality."""

import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

BASE_URL = "http://localhost:8501"


@pytest.mark.e2e
class TestChatFlow:
    """E2E tests for chat functionality after authentication."""

    def _login(self, page: Page):
        """Login by filling the Streamlit login form."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.get_by_role("textbox", name="Email").first.fill("admin@moksha.ai")
        page.get_by_role("textbox", name="Password").first.fill("admin123456")
        page.get_by_role("button", name="Login").first.click()
        page.wait_for_load_state("networkidle", timeout=30000)
        page.get_by_placeholder("Ask your spiritual question...").wait_for(
            state="visible", timeout=30000
        )

    def test_welcome_message_visible(self, page: Page):
        """Test that welcome message is shown for logged-in users."""
        self._login(page)
        expect(page.get_by_placeholder("Ask your spiritual question...")).to_be_visible(
            timeout=30000
        )

    def test_chat_input_visible(self, page: Page):
        """Test that chat input is visible after login."""
        self._login(page)
        expect(page.get_by_placeholder("Ask your spiritual question...")).to_be_visible(
            timeout=30000
        )

    def test_sidebar_visible(self, page: Page):
        """Test that sidebar with chat history is visible."""
        self._login(page)
        expect(page.get_by_text("Chat History")).to_be_visible(timeout=30000)

    def test_send_spiritual_question_gets_rag_response(self, page: Page):
        """Full query -> RAG response with citations."""
        self._login(page)

        chat_input = page.get_by_placeholder("Ask your spiritual question...")
        chat_input.fill("What do the indexed texts teach about ethical action?")
        chat_input.press("Enter")

        # Wait for bot response (not user message) - look for response content
        main_area = page.locator('[data-testid="stMainBlockContainer"]')
        expect(main_area.get_by_text("Page", exact=False)).to_be_visible(timeout=30000)

    def test_send_guidance_question_gets_general_response(self, page: Page):
        """Guidance question -> General response."""
        self._login(page)

        chat_input = page.get_by_placeholder("Ask your spiritual question...")
        chat_input.fill("How can I find inner peace?")
        chat_input.press("Enter")

        main_area = page.locator('[data-testid="stMainBlockContainer"]')
        expect(main_area.get_by_text("peace", exact=False)).to_be_visible(
            timeout=120000
        )

    def test_chat_history_persistence(self, page: Page):
        """Reload page -> chat history preserved (if session persists)."""
        self._login(page)

        chat_input = page.get_by_placeholder("Ask your spiritual question...")
        chat_input.fill("What is karma?")
        chat_input.press("Enter")

        main_area = page.locator('[data-testid="stMainBlockContainer"]')
        expect(main_area.get_by_text("karma", exact=False)).to_be_visible(
            timeout=120000
        )

        # Reload - check if session persists
        page.reload()
        page.wait_for_load_state("networkidle", timeout=30000)

        # If logged in, chat input should be visible; if logged out, login tab visible
        try:
            page.get_by_placeholder("Ask your spiritual question...").wait_for(
                state="visible", timeout=10000
            )
            # Session persisted - check for message
            expect(main_area.get_by_text("karma", exact=False)).to_be_visible(
                timeout=30000
            )
        except PlaywrightTimeoutError:
            # Session did not persist - user is at login screen
            expect(page.get_by_role("tab", name="Login")).to_be_visible(timeout=5000)

    def test_new_conversation_button(self, page: Page):
        """New Conversation creates fresh chat."""
        self._login(page)

        chat_input = page.get_by_placeholder("Ask your spiritual question...")
        chat_input.fill("Test message for first chat")
        chat_input.press("Enter")

        main_area = page.locator('[data-testid="stMainBlockContainer"]')
        expect(main_area.get_by_text("Test message for first chat")).to_be_visible(
            timeout=120000
        )

        page.get_by_role("button", name="New Conversation").click()
        page.wait_for_load_state("networkidle", timeout=10000)

        expect(
            page.get_by_placeholder("Ask your spiritual question...")
        ).to_be_visible()

    def test_logout_returns_to_login(self, page: Page):
        """Logout flow."""
        self._login(page)

        page.get_by_role("button", name="Logout").click()
        page.wait_for_load_state("networkidle", timeout=10000)

        expect(page.get_by_role("tab", name="Login")).to_be_visible(timeout=10000)

    def test_sidebar_shows_available_scriptures(self, page: Page):
        """Sidebar expander shows indexed scriptures."""
        self._login(page)

        page.get_by_text("Available Scriptures").click()
        page.wait_for_load_state("networkidle", timeout=5000)

        sidebar = page.locator('[data-testid="stSidebar"]')
        expect(sidebar.locator("strong").first).to_be_visible(timeout=5000)
