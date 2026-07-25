"""
HTTP client for communicating with the Django REST API.

This module replaces the old direct imports from core/ with HTTP calls
to the Django backend, enabling clean separation between frontend and backend.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

logger = logging.getLogger("streamlit_ui.api_client")


class MokshaAPIClient:
    """Client for the Moksha AI Django REST API."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("DJANGO_API_URL", "http://localhost:8000")
        self.session = requests.Session()
        self._load_tokens()

    def _load_tokens(self) -> None:
        """Load tokens from Streamlit session state."""
        self.access_token = st.session_state.get("access_token", "")
        self.refresh_token = st.session_state.get("refresh_token", "")

    def _save_tokens(self, access: str, refresh: str) -> None:
        """Save tokens to Streamlit session state."""
        st.session_state["access_token"] = access
        st.session_state["refresh_token"] = refresh
        self.access_token = access
        self.refresh_token = refresh

    def _clear_tokens(self) -> None:
        """Clear tokens from Streamlit session state."""
        st.session_state.pop("access_token", None)
        st.session_state.pop("refresh_token", None)
        self.access_token = ""
        self.refresh_token = ""

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        self._load_tokens()
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _refresh_access_token(self) -> bool:
        """Attempt to refresh the access token."""
        if not self.refresh_token:
            return False
        try:
            resp = self.session.post(
                f"{self.base_url}/api/auth/refresh/",
                json={"refresh": self.refresh_token},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._save_tokens(
                    data["access"], data.get("refresh", self.refresh_token)
                )
                return True
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
        return False

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        retry: bool = True,
        timeout: int = 30,
    ) -> requests.Response:
        """Make an authenticated API request."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        resp = self.session.request(
            method,
            url,
            json=data,
            headers=headers,
            timeout=timeout,
        )

        # If unauthorized, try refreshing token
        if resp.status_code == 401 and retry:
            if self._refresh_access_token():
                headers = self._get_headers()
                resp = self.session.request(
                    method,
                    url,
                    json=data,
                    headers=headers,
                    timeout=timeout,
                )

        return resp

    # ─── Auth ──────────────────────────────────────────────────────────

    def register(
        self, email: str, password: str, spiritual_name: str = ""
    ) -> Dict[str, Any]:
        """Register a new user."""
        resp = self.session.post(
            f"{self.base_url}/api/auth/register/",
            json={
                "email": email,
                "password": password,
                "password_confirm": password,
                "spiritual_name": spiritual_name,
            },
            timeout=15,
        )
        if resp.status_code == 201:
            return {"success": True, "data": resp.json()}
        try:
            return {"success": False, "error": resp.json()}
        except Exception:
            return {"success": False, "error": {"detail": resp.text}}

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login and store JWT tokens."""
        resp = self.session.post(
            f"{self.base_url}/api/auth/login/",
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            # SimpleJWT login returns access + refresh
            if "access" in data:
                self._save_tokens(data["access"], data.get("refresh", ""))
            return {"success": True, "data": data}
        try:
            return {"success": False, "error": resp.json()}
        except Exception:
            return {"success": False, "error": {"detail": resp.text}}

    def logout(self) -> None:
        """Clear stored tokens."""
        self._clear_tokens()

    def get_profile(self) -> Optional[Dict]:
        """Get current user profile."""
        resp = self._request("GET", "/api/auth/me/")
        if resp.status_code == 200:
            return resp.json()
        return None

    def is_authenticated(self) -> bool:
        """Check if user has valid tokens."""
        self._load_tokens()
        if not self.access_token:
            return False
        profile = self.get_profile()
        return profile is not None

    # ─── Chats ─────────────────────────────────────────────────────────

    def list_chats(self) -> List[Dict]:
        """List all chats for the current user."""
        resp = self._request("GET", "/api/chat/")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get("results", [])
            return data if isinstance(data, list) else []
        return []

    def create_chat(self) -> Optional[Dict]:
        """Create a new chat session."""
        resp = self._request("POST", "/api/chat/")
        if resp.status_code == 201:
            return resp.json()
        return None

    def get_chat(self, chat_id: str) -> Optional[Dict]:
        """Get a chat with its messages."""
        resp = self._request("GET", f"/api/chat/{chat_id}/")
        if resp.status_code == 200:
            return resp.json()
        return None

    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat session."""
        resp = self._request("DELETE", f"/api/chat/{chat_id}/")
        return resp.status_code == 204

    def rename_chat(self, chat_id: str, name: str) -> bool:
        """Rename a chat session."""
        resp = self._request(
            "PATCH", f"/api/chat/{chat_id}/rename/", data={"name": name}
        )
        return resp.status_code == 200

    def query(self, chat_id: str, message: str) -> Dict[str, Any]:
        """Submit a query to the chat."""
        resp = self._request(
            "POST",
            f"/api/chat/{chat_id}/query/",
            data={"message": message},
            timeout=int(os.getenv("DJANGO_QUERY_TIMEOUT_SECONDS", "180")),
        )
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        return {
            "success": False,
            "error": resp.json() if resp.content else {"detail": resp.text},
        }

    # ─── Scriptures ────────────────────────────────────────────────────

    def list_scriptures(self) -> List[Dict]:
        """List available scriptures."""
        resp = self._request("GET", "/api/scriptures/")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get("results", [])
            return data if isinstance(data, list) else []
        return []

    def discover_scriptures(self) -> Dict:
        """Trigger scripture auto-discovery."""
        resp = self._request("POST", "/api/chat/discover/")
        return resp.json() if resp.status_code == 200 else {}

    # ─── Health ────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """Check if the API is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/api/auth/health/", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
