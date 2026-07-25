"""Playwright E2E tests for authentication flow."""

import pytest
import uuid
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8501"


@pytest.mark.e2e
class TestAuthFlow:
    """E2E tests for the login/register screen."""

    def test_page_loads(self, page: Page):
        """Test that the Streamlit page loads with Moksha AI title."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        expect(page.get_by_role("heading", name="Moksha AI")).to_be_visible()

    def test_login_tab_visible(self, page: Page):
        """Test that the Login tab is visible."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        expect(page.get_by_role("tab", name="Login")).to_be_visible()

    def test_register_tab_visible(self, page: Page):
        """Test that the Register tab is visible."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        expect(page.get_by_role("tab", name="Register")).to_be_visible()

    def test_login_form_elements(self, page: Page):
        """Test that login form has email and password fields."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        expect(page.get_by_role("textbox", name="Email").first).to_be_visible()
        expect(page.get_by_role("textbox", name="Password").first).to_be_visible()
        expect(page.get_by_role("button", name="Login").first).to_be_visible()

    def test_register_form_elements(self, page: Page):
        """Test that register form has all required fields."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        # Register form elements are in DOM but hidden - use nth(1) for second set
        expect(page.get_by_role("textbox", name="Email").nth(1)).to_be_visible()
        expect(page.get_by_role("textbox", name="Password").nth(1)).to_be_visible()
        expect(page.get_by_role("textbox", name="Confirm Password")).to_be_visible()
        expect(
            page.get_by_role("textbox", name="Spiritual Name (optional)")
        ).to_be_visible()

    def test_login_with_invalid_credentials(self, page: Page):
        """Test that login fails with invalid credentials."""
        page.goto(BASE_URL)

        email_input = page.get_by_role("textbox", name="Email").first
        email_input.fill("admin@moksha.ai")

        password_input = page.get_by_role("textbox", name="Password").first
        password_input.fill("wrongpassword123")

        login_btn = page.get_by_role("button", name="Login").first
        login_btn.click()

        expect(page.get_by_text("Login failed")).to_be_visible(timeout=10000)

    def test_login_with_valid_credentials(self, page: Page):
        """Test that valid credentials redirect to chat interface."""
        page.goto(BASE_URL)

        email_input = page.get_by_role("textbox", name="Email").first
        email_input.fill("admin@moksha.ai")

        password_input = page.get_by_role("textbox", name="Password").first
        password_input.fill("admin123456")

        login_btn = page.get_by_role("button", name="Login").first
        login_btn.click()

        expect(page.get_by_placeholder("Ask your spiritual question...")).to_be_visible(
            timeout=30000
        )

    def test_register_new_user(self, page: Page):
        """Test that a new user can register successfully."""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)

        # Use nth(1) for register form fields (second occurrence)
        email_input = page.get_by_role("textbox", name="Email").nth(1)
        email_input.fill(unique_email)

        password_input = page.get_by_role("textbox", name="Password").nth(1)
        password_input.fill("securepass123")

        confirm_password = page.get_by_role("textbox", name="Confirm Password")
        confirm_password.fill("securepass123")

        register_btn = page.get_by_role("button", name="Register").first
        register_btn.click()

        expect(page.get_by_placeholder("Ask your spiritual question...")).to_be_visible(
            timeout=15000
        )

    def test_mismatched_passwords(self, page: Page):
        """Test that mismatched passwords show error."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)

        email_input = page.get_by_role("textbox", name="Email").nth(1)
        email_input.fill(f"test_{uuid.uuid4().hex[:8]}@example.com")

        password_input = page.get_by_role("textbox", name="Password").nth(1)
        password_input.fill("password123")

        confirm_password = page.get_by_role("textbox", name="Confirm Password")
        confirm_password.fill("differentpass456")

        register_btn = page.get_by_role("button", name="Register").first
        register_btn.click()

        expect(page.get_by_text("Passwords do not match")).to_be_visible(timeout=10000)

    def test_empty_email_field(self, page: Page):
        """Test that empty email field shows validation."""
        page.goto(BASE_URL)

        login_btn = page.get_by_role("button", name="Login").first
        login_btn.click()

        expect(page.get_by_text("Please fill in all fields")).to_be_visible(
            timeout=10000
        )

    def test_short_password_rejected(self, page: Page):
        """Test that password shorter than 8 chars is rejected."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle", timeout=30000)

        email_input = page.get_by_role("textbox", name="Email").nth(1)
        email_input.fill(f"test_{uuid.uuid4().hex[:8]}@example.com")

        password_input = page.get_by_role("textbox", name="Password").nth(1)
        password_input.fill("short")

        confirm_password = page.get_by_role("textbox", name="Confirm Password")
        confirm_password.fill("short")

        register_btn = page.get_by_role("button", name="Register").first
        register_btn.click()

        expect(
            page.get_by_text("Password must be at least 8 characters")
        ).to_be_visible(timeout=10000)
