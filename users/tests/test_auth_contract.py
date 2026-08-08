"""Fast tests for browser auth contracts that must not regress."""

from unittest.mock import Mock

from users.serializers import RegisterSerializer


def test_register_duplicate_email_returns_specific_account_exists_message(monkeypatch):
    """Duplicate registration should not collapse into a vague auth failure."""
    existing = Mock()
    existing.exists.return_value = True
    monkeypatch.setattr(
        "users.serializers.User.objects.normalize_email",
        lambda email: email.lower(),
    )
    monkeypatch.setattr("users.serializers.User.objects.filter", lambda **_: existing)

    serializer = RegisterSerializer(
        data={
            "email": "EXISTING@example.com",
            "password": "securepass123",
            "password_confirm": "securepass123",
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors["email"] == ["Account already exists. Sign in instead."]


def test_register_email_is_normalized_before_create_path(monkeypatch):
    available = Mock()
    available.exists.return_value = False
    monkeypatch.setattr(
        "users.serializers.User.objects.normalize_email",
        lambda email: email.lower(),
    )
    monkeypatch.setattr("users.serializers.User.objects.filter", lambda **_: available)

    serializer = RegisterSerializer(
        data={
            "email": "NEW@example.com",
            "password": "securepass123",
            "password_confirm": "securepass123",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["email"] == "new@example.com"
