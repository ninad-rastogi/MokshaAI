"""Shared test fixtures for Moksha AI."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings_test")
django.setup()

import pytest  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from users.models import User  # noqa: E402


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def create_user():
    """Factory fixture to create users."""

    def _create_user(
        email="test@example.com",
        password="testpass123",
        spiritual_name="Test User",
    ):
        return User.objects.create_user(
            email=email,
            password=password,
            spiritual_name=spiritual_name,
        )

    return _create_user


@pytest.fixture
def authenticated_client(db):
    """Return an authenticated DRF API client."""
    client = APIClient()
    # Create user directly in DB
    email = "test@example.com"
    password = "testpass123"
    User.objects.filter(email=email).delete()
    user = User.objects.create_user(
        email=email,
        password=password,
        spiritual_name="Test User",
    )
    # Login via API to get JWT token
    response = client.post(
        "/api/auth/login/",
        {"email": email, "password": password},
    )
    if response.status_code == 200:
        token = response.json().get("access", "")
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client, user
