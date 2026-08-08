"""Nuxt browser E2E tests for the chat workspace."""

import pytest
from playwright.sync_api import Page, expect


def open_app(page: Page, base_url: str, install_mock_api) -> None:
    install_mock_api(page)
    page.goto(f"{base_url}/app", wait_until="load")
    page.get_by_label("Message Moksha AI").wait_for(timeout=15_000)


@pytest.mark.e2e
class TestChatFlow:
    def test_workspace_shell_is_static_and_ready(
        self,
        page: Page,
        base_url: str,
        install_mock_api,
    ):
        open_app(page, base_url, install_mock_api)

        expect(
            page.get_by_role("heading", name="Finding steadiness under pressure")
        ).to_be_visible()
        expect(page.get_by_label("Online · Moksha local · qwen3:4b")).to_be_visible()
        expect(page.get_by_label("Message Moksha AI")).to_be_visible()
        expect(page.get_by_text("Moksha AI may err")).to_be_visible()
        expect(page.locator("html")).not_to_have_js_property("scrollTop", 1)

    def test_sidebar_has_compact_new_chat_action(
        self,
        page: Page,
        base_url: str,
        install_mock_api,
    ):
        open_app(page, base_url, install_mock_api)
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload(wait_until="load")
        page.get_by_label("Open conversation history").click()

        new_chat = page.get_by_label("Start new conversation")
        expect(new_chat).to_contain_text("New chat")
        metrics = new_chat.evaluate("""element => {
              const label = element.querySelector('.new-chat__label');
              const rect = element.getBoundingClientRect();
              const labelRect = label.getBoundingClientRect();
              const style = getComputedStyle(label);
              return {
                height: rect.height,
                lines: Math.round(labelRect.height / parseFloat(style.lineHeight)),
                whiteSpace: style.whiteSpace
              };
            }""")
        assert metrics == {"height": 36, "lines": 1, "whiteSpace": "nowrap"}

    def test_enter_sends_message_shift_enter_adds_newline(
        self,
        page: Page,
        base_url: str,
        install_mock_api,
    ):
        open_app(page, base_url, install_mock_api)
        composer = page.get_by_label("Message Moksha AI")
        composer.fill("How can I act with steadiness?")
        composer.press("Shift+Enter")
        expect(composer).to_have_value("How can I act with steadiness?\n")
        composer.type("Please answer briefly.")
        composer.press("Enter")

        expect(page.get_by_text("How can I act with steadiness?")).to_be_visible()
        expect(composer).to_have_value("")

    def test_citation_shows_exact_verse_and_translation(
        self,
        page: Page,
        base_url: str,
        install_mock_api,
    ):
        open_app(page, base_url, install_mock_api)

        expect(page.get_by_text("1 source quotation")).to_be_visible()
        expect(page.locator(".verse-text").first).to_contain_text(
            "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।"
        )
        expect(
            page.get_by_text("Arise, awake, and learn from the wise.", exact=True)
        ).to_be_visible()

    def test_settings_models_are_account_level(
        self,
        page: Page,
        base_url: str,
        install_mock_api,
    ):
        open_app(page, base_url, install_mock_api)
        page.locator(".desktop-settings").click()

        expect(page.get_by_role("dialog", name="Settings")).to_be_visible()
        page.locator(".settings-nav").get_by_role("button", name="Models").click()
        expect(
            page.get_by_role("radio", name="Moksha local qwen3:4b Local")
        ).to_be_visible()
