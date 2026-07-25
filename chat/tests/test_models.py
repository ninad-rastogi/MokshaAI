"""Tests for Chat and Message models."""

import pytest

from chat.models import Chat, Message
from users.models import User


@pytest.mark.django_db
class TestChatModel:
    """Tests for the Chat model."""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_create_chat(self, user):
        """Test creating a chat."""
        chat = Chat.objects.create(user=user)
        assert chat.user == user
        assert chat.name == "New Spiritual Conversation"
        assert str(chat.id)  # UUID should be set

    def test_chat_ordering(self, user):
        """Test chats are ordered by updated_at descending."""
        import time

        chat1 = Chat.objects.create(user=user, name="First")
        time.sleep(0.1)  # Ensure different timestamps
        chat2 = Chat.objects.create(user=user, name="Second")
        chats = list(Chat.objects.filter(user=user))
        assert chats[0] == chat2  # Most recent first
        assert chats[1] == chat1


@pytest.mark.django_db
class TestMessageModel:
    """Tests for the Message model."""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    @pytest.fixture
    def chat(self, user):
        return Chat.objects.create(user=user)

    def test_create_message(self, chat):
        """Test creating a message."""
        msg = Message.objects.create(chat=chat, role="user", content="Hello")
        assert msg.chat == chat
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_ordering(self, chat):
        """Test messages are ordered by created_at ascending."""
        Message.objects.create(chat=chat, role="user", content="First")
        msg2 = Message.objects.create(chat=chat, role="assistant", content="Second")
        messages = list(Message.objects.filter(chat=chat))
        assert messages[0].content == "First"
        assert messages[1] == msg2
