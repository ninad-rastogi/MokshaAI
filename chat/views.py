"""Views for the chat app."""

import json
import logging
import time
from typing import cast
from uuid import UUID

from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from chat.events import format_sse, publish_run_event, redis_client
from chat.models import Chat, GenerationRun
from chat.serializers import (
    ChatDetailSerializer,
    ChatSerializer,
    GenerationRunSerializer,
    RunCreateSerializer,
)
from chat.tasks import generate_chat_response
from users.models import User

logger = logging.getLogger("chat.views")


class EventStreamRenderer(BaseRenderer):
    """Allow DRF negotiation for server-sent event responses."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class ChatCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-updated_at"


class MessageCursorPagination(CursorPagination):
    page_size = 50
    ordering = "created_at"


class ChatViewSet(viewsets.ViewSet):
    """ViewSet for chat sessions and message handling."""

    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if getattr(self, "action", None) in {"query", "runs"}:
            self.throttle_scope = "chat_query"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def list(self, request: Request) -> Response:
        """List all chats for the current user."""
        archived = request.query_params.get("archived") == "true"
        chats = Chat.objects.filter(user=cast(User, request.user), is_archived=archived)
        paginator = ChatCursorPagination()
        page = paginator.paginate_queryset(chats, request)
        serializer = ChatSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def create(self, request: Request) -> Response:
        """Create a new chat session."""
        chat = Chat.objects.create(user=cast(User, request.user))
        serializer = ChatSerializer(chat)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: UUID | None = None) -> Response:
        """Get a chat with its full message history."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        serializer = ChatDetailSerializer(chat)
        return Response(serializer.data)

    def destroy(self, request: Request, pk: UUID | None = None) -> Response:
        """Delete a chat session."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        has_active_run = chat.runs.filter(
            state__in=[GenerationRun.State.QUEUED, GenerationRun.State.RUNNING]
        ).exists()
        if has_active_run:
            return Response(
                {"error": "active_run", "detail": "Cancel the active run first."},
                status=status.HTTP_409_CONFLICT,
            )
        chat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: UUID | None = None) -> Response:
        """Archive a chat session."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        chat.is_archived = True
        chat.save(update_fields=["is_archived", "updated_at"])
        return Response(ChatSerializer(chat).data)

    @action(detail=True, methods=["post"])
    def unarchive(self, request: Request, pk: UUID | None = None) -> Response:
        """Restore an archived chat session."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        chat.is_archived = False
        chat.save(update_fields=["is_archived", "updated_at"])
        return Response(ChatSerializer(chat).data)

    @action(detail=True, methods=["get"])
    def messages(self, request: Request, pk: UUID | None = None) -> Response:
        """Cursor-paginated messages for one chat."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(chat.messages.all(), request)
        from chat.serializers import MessageSerializer

        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"], url_path="runs")
    def runs(self, request: Request, pk: UUID | None = None) -> Response:
        """Create a durable generation run."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        user = cast(User, request.user)
        serializer = RunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return Response(
                {"error": "idempotency_key_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_count = GenerationRun.objects.filter(
            user=user,
            state__in=[GenerationRun.State.QUEUED, GenerationRun.State.RUNNING],
        ).count()
        max_active = getattr(settings, "GENERATION_MAX_ACTIVE_PER_USER", 2)

        run, created = GenerationRun.objects.get_or_create(
            chat=chat,
            idempotency_key=idempotency_key,
            defaults={
                "user": user,
                "prompt": serializer.validated_data["message"],
                "model_profile": serializer.validated_data.get("model_profile", ""),
                "stream_key": f"generation:{chat.pk}:{idempotency_key}",
            },
        )
        if not created:
            return Response(
                GenerationRunSerializer(run).data, status=status.HTTP_200_OK
            )
        if active_count >= max_active:
            run.state = GenerationRun.State.FAILED
            run.error_code = "overloaded"
            run.finished_at = timezone.now()
            run.save(update_fields=["state", "error_code", "finished_at"])
            return Response(
                {"error": "overloaded", "detail": "Too many active generations."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": "10"},
            )

        publish_run_event(run.stream_key, "state", {"state": run.state})
        generate_chat_response.delay(str(run.pk))
        return Response(
            GenerationRunSerializer(run).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["patch"])
    def rename(self, request: Request, pk: UUID | None = None) -> Response:
        """Rename a chat session."""
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        new_name = request.data.get("name", "").strip()
        if not new_name:
            return Response(
                {"error": "Name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        chat.name = new_name[:50]
        chat.save(update_fields=["name"])
        return Response(ChatSerializer(chat).data)

    @action(detail=True, methods=["post"])
    def query(self, request: Request, pk: UUID | None = None) -> Response:
        """Reject the old synchronous path; clients must use durable runs."""
        get_object_or_404(Chat, pk=pk, user=request.user)
        return Response(
            {
                "error": "legacy_query_removed",
                "detail": "Create a generation run at /api/v1/chats/{id}/runs/.",
            },
            status=status.HTTP_410_GONE,
        )

    @action(detail=False, methods=["post"])
    def discover(self, request: Request) -> Response:
        """Trigger scripture auto-discovery."""
        return Response(
            {
                "status": "discovery triggered",
                "message": (
                    "Run 'python manage.py discover_scriptures' " "to index scriptures."
                ),
            }
        )

    def _auto_name(self, message: str) -> str:
        """Generate a short name for the chat based on the message."""
        words = message.split()[:4]
        name = " ".join(words)
        return name[:50] if name else "Spiritual Conversation"


class RunViewSet(viewsets.ViewSet):
    """Durable generation run endpoints."""

    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer, EventStreamRenderer]

    def retrieve(self, request: Request, pk: UUID | None = None) -> Response:
        run = get_object_or_404(GenerationRun, pk=pk, user=request.user)
        return Response(GenerationRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: UUID | None = None) -> Response:
        run = get_object_or_404(GenerationRun, pk=pk, user=request.user)
        if run.state in [
            GenerationRun.State.COMPLETED,
            GenerationRun.State.FAILED,
            GenerationRun.State.CANCELLED,
        ]:
            return Response(GenerationRunSerializer(run).data)
        run.state = GenerationRun.State.CANCELLED
        run.finished_at = timezone.now()
        run.error_code = "generation_cancelled"
        run.save(update_fields=["state", "finished_at", "error_code", "updated_at"])
        publish_run_event(run.stream_key, "state", {"state": run.state})
        done_id = publish_run_event(run.stream_key, "done", {"state": run.state})
        run.last_event_id = done_id
        run.save(update_fields=["last_event_id", "updated_at"])
        return Response(GenerationRunSerializer(run).data)

    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: UUID | None = None) -> StreamingHttpResponse:
        run = get_object_or_404(GenerationRun, pk=pk, user=request.user)
        last_event_id = (
            request.headers.get("Last-Event-ID")
            or request.GET.get("last_event_id")
            or "0-0"
        )

        def stream():
            client = redis_client()
            next_id = last_event_id
            terminal = {
                GenerationRun.State.COMPLETED,
                GenerationRun.State.FAILED,
                GenerationRun.State.CANCELLED,
            }
            while True:
                entries = client.xread({run.stream_key: next_id}, block=15000, count=50)
                if entries:
                    for _, messages in entries:
                        for event_id, fields in messages:
                            next_id = str(event_id)
                            event_type = fields.get("type", "message")
                            data = json.loads(fields.get("data", "{}"))
                            yield format_sse(next_id, event_type, data)
                            if event_type == "done":
                                return
                else:
                    run.refresh_from_db(fields=["state", "final_text", "final_sources"])
                    if run.state in terminal:
                        payload = {
                            "state": run.state,
                            "text": run.final_text,
                            "sources": run.final_sources,
                        }
                        yield format_sse(run.last_event_id or "0-1", "done", payload)
                        return
                    yield ": keep-alive\n\n"
                    time.sleep(0.2)

        response = StreamingHttpResponse(stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
