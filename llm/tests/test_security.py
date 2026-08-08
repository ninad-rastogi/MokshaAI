"""Security tests for model platform BYOK and endpoint validation."""

import base64

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.core.exceptions import ValidationError
from django.test import override_settings

from llm.models import ModelConnection
from llm.security import (
    DecryptionFailed,
    KeyUnavailable,
    aad_for_connection,
    decrypt_secret,
    encrypt_secret,
    validate_public_https_endpoint,
)
from users.models import User


def test_byok_encryption_fails_closed_without_master_key() -> None:
    with (
        override_settings(BYOK_MASTER_KEY="", BYOK_MASTER_KEY_FILE=""),
        pytest.raises(KeyUnavailable),
    ):
        encrypt_secret("secret", b"aad")


def test_byok_round_trip_and_aad_binding(settings) -> None:
    settings.BYOK_MASTER_KEY = base64.urlsafe_b64encode(
        AESGCM.generate_key(256)
    ).decode("ascii")
    settings.BYOK_MASTER_KEY_FILE = ""
    nonce, ciphertext = encrypt_secret("sk-test", b"aad-1")
    assert decrypt_secret(nonce, ciphertext, b"aad-1") == "sk-test"
    with pytest.raises(DecryptionFailed):
        decrypt_secret(nonce, ciphertext, b"aad-2")


def test_byok_keyring_selects_explicit_versions(settings, tmp_path) -> None:
    first = base64.urlsafe_b64encode(AESGCM.generate_key(256)).decode("ascii")
    second = base64.urlsafe_b64encode(AESGCM.generate_key(256)).decode("ascii")
    keyring = tmp_path / "byok-keyring.json"
    keyring.write_text(
        ('{"active_version":2,"keys":{"1":"' + first + '","2":"' + second + '"}}'),
        encoding="utf-8",
    )
    settings.BYOK_KEYRING_FILE = str(keyring)
    nonce, ciphertext = encrypt_secret("secret", b"v1", key_version=1)
    assert (
        decrypt_secret(
            nonce,
            ciphertext,
            b"v1",
            key_version=1,
        )
        == "secret"
    )
    with pytest.raises(DecryptionFailed):
        decrypt_secret(
            nonce,
            ciphertext,
            b"v1",
            key_version=2,
        )


def test_public_endpoint_validation_blocks_private_hosts() -> None:
    with pytest.raises(ValidationError):
        validate_public_https_endpoint(
            "https://localhost:11434",
            resolved_ips=["127.0.0.1"],
        )
    with pytest.raises(ValidationError):
        validate_public_https_endpoint(
            "http://api.example.com",
            resolved_ips=["93.184.216.34"],
        )
    with pytest.raises(ValidationError):
        validate_public_https_endpoint(
            "https://169.254.169.254/latest/meta-data",
            resolved_ips=["169.254.169.254"],
        )


def test_public_endpoint_validation_rejects_bad_dns_pins_and_ports() -> None:
    with pytest.raises(ValidationError) as invalid_pin:
        validate_public_https_endpoint(
            "https://api.example.com",
            resolved_ips=["not-an-ip"],
        )
    assert invalid_pin.value.messages == ["endpoint_dns_invalid"]

    with pytest.raises(ValidationError) as invalid_port:
        validate_public_https_endpoint(
            "https://api.example.com:11434",
            resolved_ips=["93.184.216.34"],
        )
    assert invalid_port.value.messages == ["endpoint_port_forbidden"]


def test_public_endpoint_validation_allows_public_https() -> None:
    result = validate_public_https_endpoint(
        "https://api.example.com/v1/?token=secret#fragment",
        resolved_ips=["93.184.216.34"],
    )
    assert result.normalized_url == "https://api.example.com/v1"
    assert result.resolved_ips == ("93.184.216.34",)


@pytest.mark.django_db
def test_model_connection_encrypts_secret_bound_to_user(settings) -> None:
    settings.BYOK_MASTER_KEY = base64.urlsafe_b64encode(
        AESGCM.generate_key(256)
    ).decode("ascii")
    settings.BYOK_MASTER_KEY_FILE = ""
    user = User.objects.create_user(email="byok@example.test", password="pass")
    connection = ModelConnection.objects.create(
        user=user,
        name="OpenAI Compatible",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        dns_pins=["93.184.216.34"],
        remote_data_consent_at="2026-07-26T00:00:00Z",
    )
    connection.set_api_key("sk-live")
    connection.save(update_fields=["api_key_nonce", "encrypted_api_key"])
    assert connection.get_api_key() == "sk-live"
    bad_aad = aad_for_connection(
        user.pk, str(connection.pk), connection.key_version + 1
    )
    with pytest.raises(DecryptionFailed):
        decrypt_secret(connection.api_key_nonce, connection.encrypted_api_key, bad_aad)
