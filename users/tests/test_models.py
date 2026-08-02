"""Tests for the User model."""

import pytest

from users.models import User


@pytest.mark.django_db
class TestUserModel:
    """Tests for the custom User model."""

    def test_create_user(self):
        """Test creating a basic user."""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
        )
        assert user.is_staff
        assert user.is_superuser

    def test_email_is_required(self):
        """Test that email is required."""
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="testpass123")

    def test_email_must_be_unique(self):
        """Test that email must be unique."""
        User.objects.create_user(email="test@example.com", password="testpass123")
        with pytest.raises(Exception):
            User.objects.create_user(email="test@example.com", password="otherpass123")

    def test_user_str(self):
        """Test user string representation."""
        user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        assert str(user) == "test@example.com"

    def test_spiritual_name_optional(self):
        """Test that spiritual_name is optional."""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            spiritual_name="Ananda",
        )
        assert user.spiritual_name == "Ananda"

    def test_user_without_spiritual_name(self):
        """Test user without spiritual name has empty string."""
        user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        assert user.spiritual_name == ""
