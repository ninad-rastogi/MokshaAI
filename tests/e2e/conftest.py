"""Playwright E2E fixtures for the Nuxt product frontend."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import requests
from playwright.sync_api import Page, Route

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
NUXT_OUTPUT = FRONTEND_ROOT / ".output" / "server" / "index.mjs"
NUXT_URL = os.environ.get("NUXT_E2E_URL", "http://127.0.0.1:3057")
NOW = "2026-08-08T00:00:00Z"


def wait_for_server(url: str, timeout: int = 90) -> bool:
    """Wait for Nuxt to accept browser traffic."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if requests.get(url, timeout=2).status_code == 200:
                return True
        except requests.RequestException:
            time.sleep(1)
            continue
        time.sleep(1)
    return False


@pytest.fixture(scope="session")
def nuxt_server():
    """Start Nuxt unless NUXT_E2E_URL points at an existing server."""
    if os.environ.get("NUXT_E2E_URL"):
        if not wait_for_server(NUXT_URL, timeout=10):
            raise RuntimeError(f"NUXT_E2E_URL is not reachable: {NUXT_URL}")
        yield NUXT_URL
        return

    log_dir = PROJECT_ROOT / ".tmp" / "e2e-nuxt"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "stdout.log"
    stderr_path = log_dir / "stderr.log"

    if not NUXT_OUTPUT.exists():
        subprocess.run(
            ["npm", "run", "build"],
            cwd=FRONTEND_ROOT,
            check=True,
            stdout=stdout_path.open("w", encoding="utf-8"),
            stderr=stderr_path.open("w", encoding="utf-8"),
            text=True,
        )

    env = os.environ.copy()
    env.update(
        {
            "HOST": "127.0.0.1",
            "NITRO_HOST": "127.0.0.1",
            "NITRO_PORT": "3057",
            "PORT": "3057",
        }
    )
    stdout_file = stdout_path.open("a", encoding="utf-8")
    stderr_file = stderr_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        ["node", str(NUXT_OUTPUT)],
        cwd=FRONTEND_ROOT,
        env=env,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
    )

    try:
        if not wait_for_server(NUXT_URL):
            raise RuntimeError(
                "Nuxt server failed to start\n"
                f"stdout:\n{stdout_path.read_text(encoding='utf-8', errors='replace')}\n"
                f"stderr:\n{stderr_path.read_text(encoding='utf-8', errors='replace')}"
            )
        yield NUXT_URL
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        stdout_file.close()
        stderr_file.close()


@pytest.fixture(scope="session")
def base_url(nuxt_server: str) -> str:
    return nuxt_server


def api_payloads() -> dict[str, Any]:
    user = {
        "id": 1,
        "email": "ninadrastogi@gmail.com",
        "spiritual_name": "",
        "preferred_theme": "dark",
        "created_at": NOW,
    }
    local_profile = {
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
    chat = {
        "id": "chat-one",
        "name": "Finding steadiness under pressure",
        "is_archived": False,
        "created_at": NOW,
        "updated_at": NOW,
        "message_count": 2,
    }
    messages = [
        {
            "id": 1,
            "role": "user",
            "content": "I feel pulled in too many directions.",
            "mode": "",
            "sources": [],
            "created_at": NOW,
        },
        {
            "id": 2,
            "role": "assistant",
            "content": "Begin with one honest duty and release the outcome.",
            "mode": "grounded",
            "sources": [
                {
                    "scripture": "Katha Upanishad",
                    "page": 42,
                    "file_name": "katha-upanishad.pdf",
                    "score": 0.91,
                    "excerpt": "Sanskrit verse: उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।\nTranslation: Arise, awake, and learn from the wise.",
                    "source_text": "Sanskrit verse: उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।\nTranslation: Arise, awake, and learn from the wise.",
                    "verse_text": "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
                    "sanskrit_text": "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
                    "translation": "Arise, awake, and learn from the wise.",
                }
            ],
            "created_at": NOW,
        },
    ]
    return {
        "user": user,
        "local_profile": local_profile,
        "chat": chat,
        "messages": messages,
    }


def fulfill(route: Route, payload: Any, status: int = 200) -> None:
    route.fulfill(status=status, json=payload)


@pytest.fixture
def install_mock_api() -> Callable[[Page, bool], None]:
    def install(page: Page, authenticated: bool = True) -> None:
        payloads = api_payloads()
        state = {"authenticated": authenticated}

        def handler(route: Route) -> None:
            request = route.request
            path = request.url.split("?", 1)[0]
            method = request.method
            if path.endswith("/auth/csrf/"):
                fulfill(route, {"csrfToken": "mock-csrf"})
            elif path.endswith("/auth/me/") and state["authenticated"]:
                fulfill(route, payloads["user"])
            elif path.endswith("/auth/me/"):
                fulfill(
                    route,
                    {"detail": "Authentication credentials were not provided."},
                    401,
                )
            elif path.endswith("/auth/session/login/"):
                state["authenticated"] = True
                fulfill(route, payloads["user"])
            elif path.endswith("/auth/register/"):
                state["authenticated"] = True
                fulfill(route, payloads["user"], 201)
            elif path.endswith("/auth/session/logout/"):
                route.fulfill(status=204, body="")
            elif path.endswith("/chats/") and method == "GET":
                fulfill(
                    route,
                    {"next": None, "previous": None, "results": [payloads["chat"]]},
                )
            elif path.endswith("/chats/") and method == "POST":
                fulfill(route, payloads["chat"], 201)
            elif path.endswith("/messages/"):
                fulfill(
                    route,
                    {"next": None, "previous": None, "results": payloads["messages"]},
                )
            elif path.endswith("/runs/") and "/chats/" in path and method == "POST":
                fulfill(
                    route,
                    {
                        "id": "run-one",
                        "chat": payloads["chat"]["id"],
                        "state": "completed",
                        "model_profile": payloads["local_profile"]["id"],
                        "last_event_id": "1",
                        "final_text": "",
                        "final_sources": [],
                        "error_code": "",
                        "queued_at": NOW,
                        "started_at": NOW,
                        "finished_at": NOW,
                    },
                    201,
                )
            elif path.endswith("/runs/run-one/events/"):
                route.fulfill(
                    status=200,
                    content_type="text/event-stream",
                    body=(
                        "id: 1\n"
                        "event: done\n"
                        'data: {"final_text":"Begin with one honest duty.","sources":[]}\n\n'
                    ),
                )
            elif path.endswith("/models/profiles/"):
                fulfill(
                    route,
                    {
                        "next": None,
                        "previous": None,
                        "results": [payloads["local_profile"]],
                    },
                )
            elif path.endswith("/models/preferences/me/"):
                fulfill(
                    route,
                    {
                        "primary_profile": payloads["local_profile"]["id"],
                        "primary_profile_detail": payloads["local_profile"],
                        "ordered_fallback_profile_ids": [],
                        "updated_at": NOW,
                    },
                )
            elif path.endswith("/scriptures/"):
                fulfill(route, {"next": None, "previous": None, "results": []})
            else:
                fulfill(route, {"detail": f"Unhandled {method} {path}"}, 404)

        page.route("**/api/v1/**", handler)

    return install


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: end-to-end Nuxt browser tests")
