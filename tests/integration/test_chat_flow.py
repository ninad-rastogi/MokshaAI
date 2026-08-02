"""Integration tests for the browser chat flow."""

from unittest.mock import patch

import pytest
from rest_framework import status

from chat.models import Chat, GenerationRun, Message


@pytest.mark.django_db
class TestChatFlow:
    """End-to-end browser flow over the production v1 API."""

    def test_full_flow(self, api_client):
        """Register, keep session auth, create/cancel a durable run, and manage chat."""
        reg_resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "flow@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
            },
            format="json",
        )
        assert reg_resp.status_code == status.HTTP_201_CREATED

        duplicate_resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "FLOW@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
            },
            format="json",
        )
        assert duplicate_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert duplicate_resp.json()["email"] == [
            "Account already exists. Sign in instead."
        ]

        login_resp = api_client.post(
            "/api/v1/auth/session/login/",
            {
                "email": "flow@example.com",
                "password": "securepass123",
            },
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK

        profile_resp = api_client.get("/api/v1/auth/me/")
        assert profile_resp.status_code == status.HTTP_200_OK
        assert profile_resp.data["email"] == "flow@example.com"

        refresh_client = api_client.__class__()
        refresh_client.cookies = api_client.cookies
        refresh_resp = refresh_client.get("/api/v1/auth/me/")
        assert refresh_resp.status_code == status.HTTP_200_OK
        assert refresh_resp.data["email"] == "flow@example.com"

        chat_resp = api_client.post("/api/v1/chats/", format="json")
        assert chat_resp.status_code == status.HTTP_201_CREATED
        chat_id = chat_resp.data["id"]

        list_resp = api_client.get("/api/v1/chats/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["results"][0]["id"] == chat_id

        with (
            patch("chat.views.generate_chat_response.delay") as delay,
            patch("chat.views.publish_run_event", return_value="1-0"),
        ):
            run_resp = api_client.post(
                f"/api/v1/chats/{chat_id}/runs/",
                {"message": "What is dharma?"},
                HTTP_IDEMPOTENCY_KEY="flow-run-1",
                format="json",
            )
            duplicate_run_resp = api_client.post(
                f"/api/v1/chats/{chat_id}/runs/",
                {"message": "What is dharma?"},
                HTTP_IDEMPOTENCY_KEY="flow-run-1",
                format="json",
            )

        assert run_resp.status_code == status.HTTP_202_ACCEPTED
        assert duplicate_run_resp.status_code == status.HTTP_200_OK
        assert run_resp.data["id"] == duplicate_run_resp.data["id"]
        assert run_resp.data["state"] == GenerationRun.State.QUEUED
        assert delay.call_count == 1
        assert not Message.objects.filter(chat_id=chat_id).exists()

        delete_active_resp = api_client.delete(f"/api/v1/chats/{chat_id}/")
        assert delete_active_resp.status_code == status.HTTP_409_CONFLICT
        assert delete_active_resp.json()["error"] == "active_run"

        with patch("chat.views.publish_run_event", side_effect=["2-0", "3-0"]):
            cancel_resp = api_client.post(f"/api/v1/runs/{run_resp.data['id']}/cancel/")
        assert cancel_resp.status_code == status.HTTP_200_OK
        assert cancel_resp.data["state"] == GenerationRun.State.CANCELLED

        detail_resp = api_client.get(f"/api/v1/chats/{chat_id}/")
        assert detail_resp.status_code == status.HTTP_200_OK

        rename_resp = api_client.patch(
            f"/api/v1/chats/{chat_id}/rename/",
            {"name": "Dharma Question"},
            format="json",
        )
        assert rename_resp.status_code == status.HTTP_200_OK
        assert rename_resp.data["name"] == "Dharma Question"

        archive_resp = api_client.post(f"/api/v1/chats/{chat_id}/archive/")
        assert archive_resp.status_code == status.HTTP_200_OK
        assert archive_resp.data["is_archived"] is True

        archived_resp = api_client.get("/api/v1/chats/?archived=true")
        assert archived_resp.status_code == status.HTTP_200_OK
        assert archived_resp.data["results"][0]["id"] == chat_id

        restore_resp = api_client.post(f"/api/v1/chats/{chat_id}/unarchive/")
        assert restore_resp.status_code == status.HTTP_200_OK
        assert restore_resp.data["is_archived"] is False

        delete_resp = api_client.delete(f"/api/v1/chats/{chat_id}/")
        assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Chat.objects.filter(id=chat_id).exists()
