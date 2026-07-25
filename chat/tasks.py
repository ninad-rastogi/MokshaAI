"""Celery tasks for durable chat generation."""

import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chat.events import publish_run_event
from chat.models import GenerationAttempt, GenerationRun, Message
from chat.rag.embeddings import PgVectorStore
from chat.rag.engine import RAGEngine
from scriptures.models import Scripture

logger = logging.getLogger("chat.tasks")


def _public_error(code: str) -> dict[str, str]:
    messages = {
        "generation_cancelled": "This response was cancelled.",
        "generation_failed": (
            "I could not complete that response. Please retry in a moment."
        ),
    }
    return {"code": code, "message": messages.get(code, messages["generation_failed"])}


@shared_task(bind=True, queue="generation")
def generate_chat_response(self, run_id: str) -> None:
    """Generate one assistant message for a durable run."""
    try:
        run = GenerationRun.objects.select_related("chat", "user").get(pk=run_id)
    except GenerationRun.DoesNotExist:
        logger.warning("Generation run %s no longer exists", run_id)
        return

    if run.state == GenerationRun.State.CANCELLED:
        publish_run_event(run.stream_key, "state", {"state": run.state})
        return

    with transaction.atomic():
        run = (
            GenerationRun.objects.select_for_update()
            .select_related("chat", "user")
            .get(pk=run_id)
        )
        if run.state == GenerationRun.State.CANCELLED:
            publish_run_event(run.stream_key, "state", {"state": run.state})
            return
        if not run.user_message_id:
            run.user_message = Message.objects.create(
                chat=run.chat,
                role="user",
                content=run.prompt,
            )
        run.state = GenerationRun.State.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["user_message", "state", "started_at", "updated_at"])

    event_id = publish_run_event(run.stream_key, "state", {"state": run.state})
    GenerationRun.objects.filter(pk=run.pk).update(last_event_id=event_id)

    attempt = GenerationAttempt.objects.create(
        run=run,
        attempt_number=1,
        provider="ollama",
        model=run.model_profile or settings.OLLAMA_MODEL,
        model_snapshot={
            "base_url": settings.OLLAMA_BASE_URL,
            "profile": run.model_profile or "",
        },
    )

    try:
        recent_query = Message.objects.filter(chat=run.chat).order_by("created_at")
        if run.user_message_id is not None:
            recent_query = recent_query.exclude(pk=run.user_message_id)
        recent_messages = [{"role": m.role, "content": m.content} for m in recent_query]
        available_scriptures = list(
            Scripture.objects.filter(is_indexed=True).values_list("name", flat=True)
        )
        engine = RAGEngine(
            vector_store=PgVectorStore(),
            ollama_model=run.model_profile or settings.OLLAMA_MODEL,
            ollama_server=settings.OLLAMA_BASE_URL,
            system_prompt=settings.VEDIC_SYSTEM_PROMPT,
            available_scriptures=available_scriptures,
        )
        route, requires_scripture = engine.route_query(run.prompt)
        sources: list[dict[str, Any]]
        if route == "safety":
            response_text = engine.query_without_rag(run.prompt, recent_messages)
            sources = []
            mode = "SAFETY"
        elif route == "rag" and requires_scripture:
            response_text, sources = engine.query_with_rag(run.prompt, recent_messages)
            mode = "RAG"
        else:
            response_text = engine.query_without_rag(run.prompt, recent_messages)
            sources = []
            mode = "GENERAL"

        run.refresh_from_db(fields=["state"])
        if run.state == GenerationRun.State.CANCELLED:
            attempt.outcome = GenerationAttempt.Outcome.CANCELLED
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=["outcome", "finished_at"])
            publish_run_event(run.stream_key, "state", {"state": run.state})
            return

        assistant_message = Message.objects.create(
            chat=run.chat,
            role="assistant",
            content=response_text,
            mode=mode,
            sources=sources,
        )
        delta_id = publish_run_event(
            run.stream_key,
            "delta",
            {"text": response_text, "message_id": assistant_message.pk},
        )
        for source in sources:
            publish_run_event(run.stream_key, "citation", source)
        done_id = publish_run_event(
            run.stream_key,
            "done",
            {
                "state": GenerationRun.State.COMPLETED,
                "message_id": assistant_message.pk,
            },
        )

        attempt.outcome = GenerationAttempt.Outcome.SUCCEEDED
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=["outcome", "finished_at"])
        GenerationRun.objects.filter(pk=run.pk).update(
            state=GenerationRun.State.COMPLETED,
            assistant_message=assistant_message,
            final_text=response_text,
            final_sources=sources,
            last_event_id=done_id or delta_id,
            finished_at=timezone.now(),
        )
    except Exception:
        logger.exception("Generation failed for run %s", run_id)
        code = "generation_failed"
        attempt.outcome = GenerationAttempt.Outcome.FAILED
        attempt.error_code = code
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=["outcome", "error_code", "finished_at"])
        error_id = publish_run_event(run.stream_key, "error", _public_error(code))
        publish_run_event(run.stream_key, "done", {"state": GenerationRun.State.FAILED})
        GenerationRun.objects.filter(pk=run.pk).update(
            state=GenerationRun.State.FAILED,
            error_code=code,
            last_event_id=error_id,
            finished_at=timezone.now(),
        )
