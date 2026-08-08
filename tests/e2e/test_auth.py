"""Nuxt browser E2E tests for authentication shell behavior."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestAuthFlow:
    def test_auth_page_loads_with_product_copy(self, page: Page, base_url: str):
        page.goto(base_url, wait_until="load")

        expect(
            page.get_by_role("heading", name="Bring what feels difficult to carry.")
        ).to_be_visible()
        expect(page.get_by_role("tab", name="Sign in")).to_be_visible()
        expect(page.get_by_role("tab", name="Create account")).to_be_visible()
        expect(page.get_by_label("Email")).to_be_visible()
        expect(page.locator("#password")).to_be_visible()

    def test_register_validation_stays_client_side(self, page: Page, base_url: str):
        page.goto(base_url, wait_until="load")
        page.get_by_role("tab", name="Create account").click()
        page.get_by_label("Email").fill("new@example.com")
        page.locator("#password").fill("password123")
        page.locator("#password-confirm").fill("different123")
        page.locator(".continue-button").click()

        expect(page.get_by_role("alert")).to_contain_text("Passwords do not match")

    def test_register_enters_app_and_refresh_keeps_session(
        self,
        page: Page,
        base_url: str,
        install_mock_api,
    ):
        install_mock_api(page, False)
        page.goto(base_url, wait_until="load")
        page.get_by_role("tab", name="Create account").click()
        page.get_by_label("Email").fill("new@example.com")
        page.locator("#password").fill("password123")
        page.locator("#password-confirm").fill("password123")
        page.locator(".continue-button").click()

        page.get_by_label("Message Moksha AI").wait_for(timeout=15_000)
        page.reload(wait_until="load")

        expect(page).to_have_url(f"{base_url}/app")
        expect(page.get_by_label("Message Moksha AI")).to_be_visible()

    def test_existing_account_register_error_shows_specific_message(
        self,
        page: Page,
        base_url: str,
    ):
        page.route(
            "**/api/v1/auth/csrf/",
            lambda route: route.fulfill(json={"csrfToken": "mock-csrf"}),
        )
        page.route(
            "**/api/v1/auth/me/",
            lambda route: route.fulfill(
                status=401,
                json={"detail": "Authentication credentials were not provided."},
            ),
        )
        page.route(
            "**/api/v1/auth/register/",
            lambda route: route.fulfill(
                status=400,
                json={"email": ["A user with that email already exists."]},
            ),
        )
        page.goto(base_url, wait_until="load")
        page.get_by_role("tab", name="Create account").click()
        page.get_by_label("Email").fill("existing@example.com")
        page.locator("#password").fill("password123")
        page.locator("#password-confirm").fill("password123")
        page.locator(".continue-button").click()

        expect(page.get_by_role("alert")).to_contain_text("already exists")
