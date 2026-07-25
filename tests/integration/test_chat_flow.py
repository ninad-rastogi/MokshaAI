"""Integration tests for the complete chat flow."""

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestChatFlow:
    """End-to-end test: register → login → create chat → query."""

    def test_full_flow(self, api_client):
        """Test the complete user journey."""
        # 1. Register
        reg_resp = api_client.post(
            "/api/auth/register/",
            {
                "email": "flow@example.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
            },
        )
        assert reg_resp.status_code == status.HTTP_201_CREATED

        # 2. Login
        login_resp = api_client.post(
            "/api/auth/login/",
            {
                "email": "flow@example.com",
                "password": "securepass123",
            },
        )
        assert login_resp.status_code == status.HTTP_200_OK
        token = login_resp.json().get("access", "")
        assert token

        # 3. Set auth
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # 4. Get profile
        profile_resp = api_client.get("/api/auth/me/")
        assert profile_resp.status_code == status.HTTP_200_OK
        assert profile_resp.data["email"] == "flow@example.com"

        # 5. Create chat
        chat_resp = api_client.post("/api/chat/")
        assert chat_resp.status_code == status.HTTP_201_CREATED
        chat_id = chat_resp.data["id"]

        # 6. List chats
        list_resp = api_client.get("/api/chat/")
        assert list_resp.status_code == status.HTTP_200_OK

        # 7. Query chat (will get placeholder response)
        query_resp = api_client.post(
            f"/api/chat/{chat_id}/query/",
            {"message": "What is dharma?"},
        )
        assert query_resp.status_code == status.HTTP_200_OK
        assert "response" in query_resp.data

        # 8. Get chat with messages
        detail_resp = api_client.get(f"/api/chat/{chat_id}/")
        assert detail_resp.status_code == status.HTTP_200_OK
        assert len(detail_resp.data["messages"]) >= 2

        # 9. Rename chat
        rename_resp = api_client.patch(
            f"/api/chat/{chat_id}/rename/",
            {"name": "Dharma Question"},
        )
        assert rename_resp.status_code == status.HTTP_200_OK

        # 10. Delete chat
        delete_resp = api_client.delete(f"/api/chat/{chat_id}/")
        assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
