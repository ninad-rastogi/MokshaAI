"""Tests for user authentication views."""

import pytest
from rest_framework import status


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
class TestProfileView:
    """Tests for the profile endpoint."""

    def test_get_profile_authenticated(self, authenticated_client):
        """Test getting profile when authenticated."""
        client, user = authenticated_client
        response = client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_get_profile_unauthenticated(self, api_client):
        """Test getting profile without authentication."""
        response = api_client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestHealthCheck:
    """Tests for the health check endpoint."""

    def test_health_check(self, api_client):
        """Test health check returns 200."""
        response = api_client.get("/api/auth/health/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
