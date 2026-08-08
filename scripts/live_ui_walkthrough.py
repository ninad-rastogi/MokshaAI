"""Exercise Moksha AI's browser-critical flows in installed Google Chrome."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def is_benign_abort(failure: dict[str, object]) -> bool:
    """Ignore browser aborts caused by deliberate navigation or dialog closure."""
    url = str(failure.get("url", ""))
    error = str(failure.get("error", ""))
    return "ERR_ABORTED" in error and (
        "/_nuxt/builds/meta/" in url
        or "/api/v1/models/connections/" in url
        or "/shutdown/pagehide" in url
    )


def geometry(page: Page) -> dict[str, object]:
    return page.evaluate("""() => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            return element ? element.getBoundingClientRect().toJSON() : null;
          };
          return {
            bodyScroll: document.documentElement.scrollHeight > innerHeight,
            viewport: [innerWidth, innerHeight],
            history: box(".history"),
            header: box(".chat-header"),
            composer: box(".composer-dock"),
            messages: box(".message-viewport"),
          };
        }""")


def _bool_result(result: dict[str, object], key: str) -> bool:
    return result.get(key) is True


def _geometry_flag(result: dict[str, object], group: str, key: str) -> bool:
    value = result.get(group)
    return isinstance(value, dict) and value.get(key) is True


def validate_result(result: dict[str, object], *, mock_api: bool) -> list[str]:
    """Return browser-critical UX contract failures."""
    failures: list[str] = []
    if "/app" not in str(result.get("auth_after_refresh", "")):
        failures.append("auth_refresh_did_not_stay_in_app")
    if not _bool_result(result, "composer_cleared"):
        failures.append("composer_did_not_clear_after_send")
    if result.get("run_state_text") != "idle":
        failures.append("run_status_not_idle_after_completion")
    if _geometry_flag(result, "desktop_geometry", "bodyScroll"):
        failures.append("desktop_body_scrolls")
    if _geometry_flag(result, "mobile_geometry", "bodyScroll"):
        failures.append("mobile_body_scrolls")
    settings_geometry = result.get("settings_geometry")
    if isinstance(settings_geometry, dict) and (
        settings_geometry.get("scroll", 0) > settings_geometry.get("client", 0) + 2
    ):
        failures.append("settings_dialog_scrolls_in_general_view")
    if result.get("console_errors"):
        failures.append("browser_console_errors")
    if result.get("request_failures"):
        failures.append("browser_request_failures")
    if mock_api:
        if result.get("connection_removed") is not True:
            failures.append("connection_remove_flow_failed")
        if result.get("primary_model_after_refresh") != "Moksha local":
            failures.append("model_preference_not_persisted_after_refresh")
        connection_status = str(result.get("connection_status_aria", ""))
        if "Online" not in connection_status or "qwen3:4b" not in connection_status:
            failures.append("model_connection_status_missing_online_model")
        if "उत्तिष्ठत जाग्रत" not in str(result.get("exact_verse_text", "")):
            failures.append("exact_verse_not_visible")
        if "Arise, awake" not in str(result.get("translation_text", "")):
            failures.append("translation_not_visible")
    return failures


def install_mock_api(page: Page) -> None:
    """Provide deterministic API state for UI review when Compose is unavailable."""
    now = "2026-07-30T12:00:00Z"
    chat: dict[str, Any] = {
        "id": "chat-1",
        "name": "Finding steadiness under pressure",
        "is_archived": False,
        "created_at": now,
        "updated_at": now,
        "message_count": 2,
    }
    citation: dict[str, Any] = {
        "scripture": "Katha Upanishad",
        "page": 42,
        "file_name": "katha-upanishad.pdf",
        "score": 0.91,
        "excerpt": "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
        "source_text": (
            "Sanskrit verse:\n"
            "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।\n\n"
            "Translation:\n"
            "Arise, awake, and learn from the wise."
        ),
        "sanskrit_text": "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
        "verse_text": "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
        "translation": "Arise, awake, and learn from the wise.",
    }
    messages: list[dict[str, Any]] = [
        {
            "id": 1,
            "role": "user",
            "content": "I feel pulled in too many directions and cannot think clearly.",
            "mode": "",
            "sources": [],
            "created_at": now,
        },
        {
            "id": 2,
            "role": "assistant",
            "content": (
                "Let us make the moment smaller. You do not need to settle "
                "every demand at once. First notice which choice is yours to "
                "make today, and which pressure can be allowed to wait."
            ),
            "mode": "grounded",
            "sources": [citation],
            "created_at": now,
        },
    ]
    local_profile: dict[str, Any] = {
        "id": "model-local",
        "name": "Moksha local",
        "model_id": "qwen3:4b",
        "connection": None,
        "connection_status": "connected",
        "connection_dialect": "builtin_ollama",
        "is_enabled": True,
        "is_admin_default": True,
        "context_window": 8192,
        "max_output_tokens": 1024,
        "temperature": 0.2,
    }
    remote_profile: dict[str, Any] = {
        "id": "model-remote",
        "name": "Personal API",
        "model_id": "wisdom-model",
        "connection": "connection-1",
        "connection_status": "connected",
        "connection_dialect": "openai_compatible",
        "is_enabled": True,
        "is_admin_default": False,
        "context_window": 16384,
        "max_output_tokens": 1024,
        "temperature": 0.2,
    }
    user: dict[str, Any] = {
        "id": 1,
        "email": "walkthrough@example.com",
        "spiritual_name": "Ninad",
        "preferred_theme": "system",
        "created_at": now,
    }
    preference: dict[str, Any] = {
        "primary_profile": local_profile["id"],
        "primary_profile_detail": local_profile,
        "ordered_fallback_profile_ids": [],
        "updated_at": now,
    }
    remote_enabled = {"value": True}

    def response(route: Route, payload: object, status: int = 200) -> None:
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload),
        )

    def handler(route: Route) -> None:
        request = route.request
        path = urlparse(request.url).path
        method = request.method
        raw_payload = request.post_data_json
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}

        if path.endswith("/auth/csrf/"):
            response(route, {"csrfToken": "mock-csrf"})
        elif path.endswith("/auth/me/"):
            if method == "PUT":
                user.update(payload)
            response(route, user)
        elif path.endswith("/auth/session/logout/"):
            route.fulfill(status=204, body="")
        elif path.endswith("/chats/") and method == "GET":
            archived = "archived=true" in request.url
            results = [] if archived != chat["is_archived"] else [chat]
            response(route, {"next": None, "previous": None, "results": results})
        elif path.endswith("/chats/") and method == "POST":
            response(route, chat, status=201)
        elif path.endswith("/messages/"):
            response(route, {"next": None, "previous": None, "results": messages})
        elif path.endswith("/rename/"):
            chat["name"] = payload["name"]
            response(route, chat)
        elif path.endswith("/archive/"):
            chat["is_archived"] = True
            response(route, chat)
        elif path.endswith("/unarchive/"):
            chat["is_archived"] = False
            response(route, chat)
        elif path.endswith("/chats/chat-1/") and method == "DELETE":
            route.fulfill(status=204, body="")
        elif path.endswith("/runs/") and "/chats/" in path:
            prompt = payload["message"]
            messages.extend(
                [
                    {
                        "id": len(messages) + 1,
                        "role": "user",
                        "content": prompt,
                        "mode": "",
                        "sources": [],
                        "created_at": now,
                    },
                    {
                        "id": len(messages) + 2,
                        "role": "assistant",
                        "content": (
                            "Begin with one honest boundary: choose the duty "
                            "that is truly yours, take its next small step, and "
                            "release the demand to control every outcome."
                        ),
                        "mode": "grounded",
                        "sources": [citation],
                        "created_at": now,
                    },
                ]
            )
            chat["message_count"] = len(messages)
            response(
                route,
                {
                    "id": "run-1",
                    "chat": chat["id"],
                    "state": "queued",
                    "model_profile": local_profile["id"],
                    "last_event_id": "",
                    "final_text": "",
                    "final_sources": [],
                    "error_code": "",
                    "queued_at": now,
                    "started_at": None,
                    "finished_at": None,
                },
                status=201,
            )
        elif path.endswith("/runs/run-1/events/"):
            events = (
                'id: 1\nevent: state\ndata: {"state":"running"}\n\n'
                'id: 2\nevent: delta\ndata: {"text":"Begin with one honest boundary."}\n\n'
                f"id: 3\nevent: citation\ndata: {json.dumps(citation)}\n\n"
                'id: 4\nevent: done\ndata: {"state":"completed"}\n\n'
            )
            route.fulfill(
                status=200,
                content_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
                body=events,
            )
        elif path.endswith("/models/profiles/"):
            response(
                route,
                {
                    "next": None,
                    "previous": None,
                    "results": [
                        local_profile,
                        *([remote_profile] if remote_enabled["value"] else []),
                    ],
                },
            )
        elif path.endswith("/models/preferences/me/"):
            if method == "PUT":
                preference["primary_profile"] = payload["primary_profile"]
                preference["ordered_fallback_profile_ids"] = payload[
                    "ordered_fallback_profile_ids"
                ]
            response(route, preference)
        elif path.endswith("/models/connections/") and method == "POST":
            response(
                route,
                {
                    "id": "connection-new",
                    "name": payload["name"],
                    "dialect": payload["dialect"],
                    "endpoint_url": payload["endpoint_url"],
                    "status": "disconnected",
                    "sanitized_detail": "Saved. Check this connection before use.",
                    "remote_data_consent_at": now,
                    "last_checked_at": None,
                    "created_at": now,
                    "updated_at": now,
                },
                status=201,
            )
        elif path.endswith("/models/connections/connection-1/") and method == "DELETE":
            remote_enabled["value"] = False
            route.fulfill(status=200, body="")
        elif path.endswith("/probe/"):
            response(
                route,
                {
                    "status": "connected",
                    "detail": "Connection verified.",
                    "models": [remote_profile["model_id"]],
                },
            )
        elif path.endswith("/scriptures/"):
            response(
                route,
                {
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "name": "Katha Upanishad",
                            "folder_path": "Katha Upanishad",
                            "is_indexed": True,
                            "total_volumes": 1,
                            "total_pages": 118,
                            "last_indexed_at": now,
                        },
                        {
                            "id": 2,
                            "name": "Yoga Sutras",
                            "folder_path": "Yoga Sutras",
                            "is_indexed": False,
                            "total_volumes": 1,
                            "total_pages": 0,
                            "last_indexed_at": None,
                        },
                    ],
                },
            )
        else:
            response(route, {"detail": f"Unhandled mock route: {method} {path}"}, 404)

    page.route("**/api/v1/**", handler)


def run(
    base_url: str,
    output_dir: Path,
    headless: bool,
    browser_channel: str,
    mock_api: bool,
    email: str | None = None,
    password: str = "MokshaWalk!2026",
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            channel=browser_channel if browser_channel != "chromium" else None,
            args=[
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
                "--ignore-certificate-errors",
            ],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        console_errors: list[str] = []
        request_failures: list[dict[str, object]] = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on(
            "requestfailed",
            lambda request: request_failures.append(
                {"url": request.url, "error": request.failure}
            ),
        )

        page.goto(base_url, wait_until="networkidle")
        body_text = page.locator("body").inner_text()
        if (
            "Kaspersky" in body_text
            and "I understand the risks and want to continue" in body_text
        ):
            page.get_by_text("I understand the risks and want to continue").click()
            page.wait_for_load_state("networkidle")
        page.screenshot(path=output_dir / "auth.png", full_page=True)
        if mock_api:
            install_mock_api(page)
            console_errors.clear()
            request_failures.clear()
            page.goto(f"{base_url.rstrip('/')}/app", wait_until="networkidle")
            page.get_by_label("Message Moksha AI").wait_for(timeout=20_000)
            page.screenshot(path=output_dir / "app-empty.png", full_page=True)
            result["auth_after_register"] = page.url
        else:
            if not page.get_by_role("tab", name="Create account").count():
                result["blocked_page"] = page.locator("body").inner_text()
                details = page.get_by_text("Show details", exact=False)
                if details.count():
                    details.first.click()
                    page.wait_for_timeout(300)
                    continue_link = page.get_by_text(
                        "I understand the risks and want to continue",
                        exact=False,
                    )
                    if continue_link.count():
                        continue_link.first.click(no_wait_after=True)
                        page.wait_for_timeout(2_000)
                        try:
                            page.wait_for_load_state("networkidle", timeout=10_000)
                        except PlaywrightTimeoutError:
                            pass
                        if page.get_by_role("tab", name="Create account").count():
                            console_errors.clear()
                            request_failures.clear()
                            page.screenshot(
                                path=output_dir / "auth.png",
                                full_page=True,
                            )
                            result["kaspersky_local_bypass"] = True
                        else:
                            result["blocked_page_after_continue"] = page.locator(
                                "body"
                            ).inner_text()
                    if page.get_by_role("tab", name="Create account").count():
                        pass
                    else:
                        result["blocked_page_details"] = page.locator(
                            "body"
                        ).inner_text()
                        page.screenshot(
                            path=output_dir / "certificate-block-details.png",
                            full_page=True,
                        )
            if page.get_by_role("tab", name="Create account").count():
                if email:
                    page.get_by_role("tab", name="Sign in").click()
                    page.get_by_label("Email").fill(email)
                    page.get_by_label("Password", exact=True).fill(password)
                    page.get_by_role("button", name="Continue").click()
                    result["auth_mode"] = "sign_in"
                else:
                    email = f"walk-{uuid.uuid4().hex[:10]}@example.com"
                    page.get_by_role("tab", name="Create account").click()
                    page.get_by_label("Email").fill(email)
                    page.get_by_label("Password", exact=True).fill(password)
                    page.get_by_label("Confirm password").fill(password)
                    page.get_by_role("button", name="Create account").last.click()
                    result["auth_mode"] = "register"
                page.wait_for_url("**/app", timeout=20_000)
                page.wait_for_load_state("networkidle")
                page.get_by_label("Message Moksha AI").wait_for(timeout=20_000)
                console_errors.clear()
                request_failures.clear()
                page.screenshot(path=output_dir / "app-empty.png", full_page=True)
                result["auth_after_register"] = page.url
            else:
                result["console_errors"] = console_errors
                result["request_failures"] = request_failures
                browser.close()
                return result

        page.reload(wait_until="networkidle")
        result["auth_after_refresh"] = page.url

        composer = page.get_by_label("Message Moksha AI")
        composer.fill(
            "I feel overwhelmed by expectations. "
            "How should I act without losing myself?"
        )
        composer.press("Enter")
        page.locator(".message--assistant").last.wait_for(timeout=60_000)
        page.locator(".run-status").wait_for(state="detached", timeout=120_000)
        page.screenshot(path=output_dir / "app-chat.png", full_page=True)
        result["composer_cleared"] = composer.input_value() == ""
        run_status = page.locator(".run-status")
        result["run_state_text"] = (
            run_status.inner_text() if run_status.count() else "idle"
        )
        result["messages"] = page.locator(".message").count()
        exact_verse = page.locator(".verse-panel").last
        translation = page.locator(".translation-panel").last
        result["exact_verse_text"] = (
            exact_verse.inner_text() if exact_verse.count() else ""
        )
        result["translation_text"] = (
            translation.inner_text() if translation.count() else ""
        )

        page.get_by_label("Open settings").last.click()
        settings = page.locator(".settings-dialog")
        settings.wait_for()
        page.screenshot(path=output_dir / "settings-general.png", full_page=True)
        result["settings_geometry"] = settings.evaluate(
            "element => ({client: element.clientHeight, scroll: element.scrollHeight})"
        )
        for section in ("Models", "Connections", "Scriptures", "Account"):
            page.get_by_role("button", name=section, exact=True).click()
            page.screenshot(
                path=output_dir / f"settings-{section.lower()}.png",
                full_page=True,
            )
            if section == "Connections":
                remove_button = page.get_by_role("button", name="Remove Personal API")
                if remove_button.count():
                    remove_button.click()
                    page.wait_for_timeout(300)
                    page.screenshot(
                        path=output_dir / "settings-remove-connection.png",
                        full_page=True,
                    )
                    page.get_by_role(
                        "button", name="Remove connection", exact=True
                    ).click()
                    page.get_by_text(
                        "Connection removed. Its encrypted credential has been revoked."
                    ).wait_for()
                    result["connection_removed"] = (
                        page.get_by_text("Personal API", exact=True).count() == 0
                    )
                else:
                    result["connection_removed"] = "no_connection_available"
        page.get_by_role("button", name="General", exact=True).click()
        page.get_by_role("radio", name="Dark").click()
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.reload(wait_until="networkidle")
        result["theme_after_refresh"] = page.locator("html").get_attribute("class")
        result["desktop_geometry"] = geometry(page)
        result["connection_status_after_refresh"] = page.locator(
            ".connection-status"
        ).inner_text()
        result["connection_status_aria"] = page.locator(
            ".connection-status"
        ).get_attribute("aria-label")
        result["primary_model_after_refresh"] = page.locator(
            ".history-footer .account-copy small"
        ).inner_text()

        page.set_viewport_size({"width": 390, "height": 844})
        page.reload(wait_until="networkidle")
        page.screenshot(path=output_dir / "mobile.png", full_page=True)
        page.get_by_label("Open conversation history").click()
        page.wait_for_timeout(350)
        page.screenshot(path=output_dir / "mobile-history.png", full_page=True)
        result["mobile_geometry"] = geometry(page)
        result["console_errors"] = console_errors
        result["request_failures"] = [
            failure
            for failure in request_failures
            if "kaspersky-labs.com" not in str(failure["url"])
            and not is_benign_abort(failure)
        ]
        result["environment_request_failures"] = [
            failure
            for failure in request_failures
            if "kaspersky-labs.com" in str(failure["url"])
            and not is_benign_abort(failure)
        ]
        browser.close()

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://localhost:8443/")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("frontend/test-results/live-walkthrough"),
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--browser-channel",
        choices=["chrome", "chromium", "msedge"],
        default="chrome",
    )
    parser.add_argument(
        "--mock-api",
        action="store_true",
        help="Exercise the UI with deterministic in-browser API responses.",
    )
    parser.add_argument("--email")
    parser.add_argument("--password", default="MokshaWalk!2026")
    args = parser.parse_args()
    result = run(
        args.base_url,
        args.output_dir,
        headless=not args.headed,
        browser_channel=args.browser_channel,
        mock_api=args.mock_api,
        email=args.email,
        password=args.password,
    )
    failures = validate_result(result, mock_api=args.mock_api)
    if failures:
        result["failures"] = failures
    print(json.dumps(result, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
