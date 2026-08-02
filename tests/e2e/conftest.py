"""Playwright E2E test fixtures for Moksha AI.

Auto-starts Django and Streamlit servers for E2E tests.
"""

import os
import subprocess
import sys
import time

import pytest
import requests

PYTHON = sys.executable

DJANGO_URL = "http://localhost:8000"
STREAMLIT_URL = "http://localhost:8501"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def wait_for_server(url: str, timeout: int = 60) -> bool:
    """Wait for a server to become responsive."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            time.sleep(1)
            continue
        time.sleep(1)
    return False


@pytest.fixture(scope="session")
def django_server():
    """Start Django development server for E2E tests."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "moksha.settings"

    proc = subprocess.Popen(
        [PYTHON, "manage.py", "runserver", "8000"],
        env=env,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if wait_for_server(f"{DJANGO_URL}/api/auth/health/"):
        yield
    else:
        stdout, stderr = proc.communicate(timeout=5)
        print("Django stdout: " + stdout.decode())
        print("Django stderr: " + stderr.decode())
        raise RuntimeError("Django server failed to start")

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def streamlit_server(django_server):
    """Start Streamlit server for E2E tests (depends on Django)."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "moksha.settings"
    env["DJANGO_API_URL"] = DJANGO_URL

    proc = subprocess.Popen(
        [
            PYTHON,
            "-m",
            "streamlit",
            "run",
            "streamlit_ui/main_app.py",
            "--server.port",
            "8501",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        env=env,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if wait_for_server(STREAMLIT_URL):
        yield
    else:
        stdout, stderr = proc.communicate(timeout=5)
        print("Streamlit stdout: " + stdout.decode())
        print("Streamlit stderr: " + stderr.decode())
        raise RuntimeError("Streamlit server failed to start")

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(autouse=True)
def _servers_ready(streamlit_server):
    """Auto-fixture to ensure servers are ready before each test."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: end-to-end browser tests (auto-starts servers)"
    )
