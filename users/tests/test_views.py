"""Tests for user authentication views."""

import pytest
from rest_framework import status

from users.views import LoginView, RegisterView, SessionLoginView


@pytest.mark.django_db
class TestRegisterView:
    """Tests for the registration endpoint."""

    def test_register_success(self, api_client):
        """Test successful user registration."""
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "newuser@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
                "spiritual_name": "New User",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "newuser@example.com"
        profile = api_client.get("/api/auth/me/")
        assert profile.status_code == status.HTTP_200_OK
        assert profile.data["email"] == "newuser@example.com"

    def test_register_password_mismatch(self, api_client):
        """Test registration with mismatched passwords."""
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "newuser@example.com",
                "password": "securepass123",
                "password_confirm": "differentpass",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client):
        """Test registration with duplicate email."""
        api_client.post(
            "/api/auth/register/",
            {
                "email": "dup@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
            },
        )
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "dup@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestSessionAuthView:
    """Tests for browser cookie-based authentication."""

    def test_session_status_is_quiet_for_anonymous_visits(self, api_client):
        """Anonymous browser visits get a 200 status probe, not a console-noisy 403."""
        response = api_client.get("/api/auth/session/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"authenticated": False, "user": None}

    def test_csrf_and_session_login(self, api_client):
        """CSRF token endpoint and session login work for browser clients."""
        register = api_client.post(
            "/api/auth/register/",
            {
                "email": "session@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
            },
        )
        assert register.status_code == status.HTTP_201_CREATED

        csrf = api_client.get("/api/auth/csrf/")
        assert csrf.status_code == status.HTTP_200_OK
        assert csrf.data["csrfToken"]

        login = api_client.post(
            "/api/auth/session/login/",
            {"email": "session@example.com", "password": "securepass123"},
        )
        assert login.status_code == status.HTTP_200_OK
        assert login.data["email"] == "session@example.com"

        profile = api_client.get("/api/auth/me/")
        assert profile.status_code == status.HTTP_200_OK

        session = api_client.get("/api/auth/session/")
        assert session.status_code == status.HTTP_200_OK
        assert session.data["authenticated"] is True
        assert session.data["user"]["email"] == "session@example.com"

    def test_auth_entrypoints_do_not_count_attempts_for_lockout(self):
        """Interactive auth should not throttle normal login/register attempts."""

        assert SessionLoginView.throttle_classes == []
        assert RegisterView.throttle_classes == []
        assert LoginView.throttle_classes == []


@pytest.mark.django_db
class TestProfileView:
    """Tests for the profile endpoint."""

    def test_get_profile_authenticated(self, authenticated_client):
        """Test getting profile when authenticated."""
        client, user = authenticated_client
        response = client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email
        assert response.data["preferred_theme"] == "system"

    def test_update_profile_persists_preferred_theme(self, authenticated_client):
        """Test account-level theme persistence."""
        client, user = authenticated_client
        response = client.put("/api/auth/me/", {"preferred_theme": "dark"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["preferred_theme"] == "dark"
        user.refresh_from_db()
        assert user.preferred_theme == "dark"

    def test_get_profile_unauthenticated(self, api_client):
        """Test getting profile without authentication."""
        response = api_client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestHealthCheck:
    """Tests for the health check endpoint."""

    def test_health_check(self, api_client):
        """Test health check returns 200."""
        response = api_client.get("/api/auth/health/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
