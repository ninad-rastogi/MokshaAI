"""Tests for model settings APIs."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from llm.models import (
    ModelCatalogRelease,
    ModelConnection,
    ModelInstallationJob,
    ModelProfile,
    UserModelPreference,
)


@pytest.mark.django_db
def test_user_model_preference_api_persists_primary_profile(authenticated_client):
    client, user = authenticated_client
    connection = ModelConnection.objects.create(
        name="Local Ollama",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    profile = ModelProfile.objects.create(
        name="User test local",
        connection=connection,
        model_id="moksha-qwen3:4b-instruct-q3km",
        is_enabled=True,
    )

    response = client.put(
        "/api/v1/models/preferences/me/",
        {"primary_profile": str(profile.pk), "ordered_fallback_profile_ids": []},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert str(response.data["primary_profile"]) == str(profile.pk)
    assert UserModelPreference.objects.get(user=user).primary_profile == profile


@pytest.mark.django_db
def test_user_connection_create_requires_remote_consent(authenticated_client):
    client, _user = authenticated_client

    response = client.post(
        "/api/v1/models/connections/",
        {
            "name": "Remote",
            "dialect": ModelConnection.Dialect.OPENAI_COMPATIBLE,
            "endpoint_url": "https://api.example.com/v1",
            "model_id": "gpt-4.1-mini",
            "api_key": "",
            "remote_data_consent": False,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_user_connection_create_adds_profile_without_replacing_preference(
    authenticated_client,
):
    client, user = authenticated_client
    local_connection = ModelConnection.objects.create(
        name="Local Ollama",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )
    local_profile = ModelProfile.objects.create(
        name="Local model",
        connection=local_connection,
        model_id="local-model",
        is_enabled=True,
    )
    UserModelPreference.objects.create(
        user=user,
        primary_profile=local_profile,
        ordered_fallback_profile_ids=[],
    )

    with patch(
        "llm.models.validate_public_https_endpoint",
        return_value=type(
            "Result",
            (),
            {
                "normalized_url": "https://api.example.com/v1",
                "resolved_ips": ("93.184.216.34",),
            },
        )(),
    ):
        response = client.post(
            "/api/v1/models/connections/",
            {
                "name": "Remote",
                "dialect": ModelConnection.Dialect.OPENAI_COMPATIBLE,
                "endpoint_url": "https://api.example.com/v1",
                "model_id": "gpt-4.1-mini",
                "api_key": "",
                "remote_data_consent": True,
            },
            format="json",
        )

    assert response.status_code == status.HTTP_201_CREATED
    connection = ModelConnection.objects.get(user=user, name="Remote")
    profile = ModelProfile.objects.get(connection=connection)
    preference = UserModelPreference.objects.get(user=user)
    assert connection.remote_data_consent_at <= timezone.now()
    assert profile.model_id == "gpt-4.1-mini"
    assert preference.primary_profile == local_profile


@pytest.mark.django_db
def test_user_can_probe_own_connection(authenticated_client):
    client, user = authenticated_client
    connection = ModelConnection.objects.create(
        user=user,
        name="User provider",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        remote_data_consent_at=timezone.now(),
    )
    probe_result = type(
        "ProbeResult",
        (),
        {
            "status": ModelConnection.Status.CONNECTED,
            "detail": "Provider probe succeeded.",
            "models": ("model-a",),
        },
    )()

    with patch("llm.views.update_connection_probe", return_value=probe_result):
        response = client.post(
            f"/api/v1/models/connections/{connection.pk}/probe/",
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == ModelConnection.Status.CONNECTED


@pytest.mark.django_db
def test_user_cannot_probe_admin_connection(authenticated_client):
    client, _user = authenticated_client
    connection = ModelConnection.objects.create(
        user=None,
        name="Managed provider",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
    )

    response = client.post(
        f"/api/v1/models/connections/{connection.pk}/probe/",
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_user_can_remove_own_connection_and_its_preferences(authenticated_client):
    client, user = authenticated_client
    connection = ModelConnection.objects.create(
        user=user,
        name="Disposable provider",
        dialect=ModelConnection.Dialect.OPENAI_COMPATIBLE,
        endpoint_url="https://api.example.com/v1",
        remote_data_consent_at=timezone.now(),
        encrypted_api_key="encrypted-secret",
        api_key_nonce="nonce",
    )
    primary = ModelProfile.objects.create(
        name="Disposable primary",
        connection=connection,
        model_id="model-a",
        is_enabled=True,
    )
    fallback = ModelProfile.objects.create(
        name="Disposable fallback",
        connection=connection,
        model_id="model-b",
        is_enabled=True,
    )
    preference = UserModelPreference.objects.create(
        user=user,
        primary_profile=primary,
        ordered_fallback_profile_ids=[str(fallback.pk)],
    )

    response = client.delete(f"/api/v1/models/connections/{connection.pk}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not ModelConnection.objects.filter(pk=connection.pk).exists()
    preference.refresh_from_db()
    assert preference.primary_profile is None
    assert preference.ordered_fallback_profile_ids == []


@pytest.mark.django_db
def test_user_cannot_remove_admin_connection(authenticated_client):
    client, _user = authenticated_client
    connection = ModelConnection.objects.create(
        user=None,
        name="Managed local provider",
        dialect=ModelConnection.Dialect.BUILTIN_OLLAMA,
        status=ModelConnection.Status.CONNECTED,
    )

    response = client.delete(f"/api/v1/models/connections/{connection.pk}/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert ModelConnection.objects.filter(pk=connection.pk).exists()


@pytest.mark.django_db
def test_non_staff_cannot_start_model_installation(authenticated_client):
    client, _user = authenticated_client

    response = client.post(
        "/api/v1/models/installations/",
        {"entry_id": "candidate", "keep_source": False},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_staff_starts_install_from_active_verified_catalog(authenticated_client):
    client, user = authenticated_client
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    entry = {
        "id": "candidate",
        "sha256": "a" * 64,
        "size": 123,
        "ollama": {
            "num_ctx": 8192,
            "num_predict": 1024,
            "temperature": 0.2,
        },
    }
    ModelCatalogRelease.objects.create(
        schema_version=1,
        sequence=1,
        version="2026.07.30.1",
        key_id="test",
        catalog_hash="b" * 64,
        signature="test",
        payload={"entries": [entry]},
        issued_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
        active=True,
    )

    with patch("llm.tasks.install_local_model.delay"):
        response = client.post(
            "/api/v1/models/installations/",
            {"entry_id": "candidate", "keep_source": False},
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    job = ModelInstallationJob.objects.get()
    assert job.catalog_entry["_catalog_version"] == "2026.07.30.1"
    assert job.source_sha256 == "a" * 64
    assert not job.keep_source
