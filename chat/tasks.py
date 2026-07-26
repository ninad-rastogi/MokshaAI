"""Celery tasks for durable chat generation."""

from dataclasses import dataclass
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
from llm.models import ModelConnection, ModelProfile
from llm.services import ModelSelection, resolve_model_selection
from scriptures.models import Scripture

logger = logging.getLogger("chat.tasks")


@dataclass(frozen=True)
class GenerationAttemptSpec:
    """One concrete provider/model attempt for a run."""

    provider: str
    model: str
    ollama_server: str
    snapshot: dict[str, Any]


def _public_error(code: str) -> dict[str, str]:
    messages = {
        "generation_cancelled": "This response was cancelled.",
        "generation_failed": (
            "I could not complete that response. Please retry in a moment."
        ),
    }
    return {"code": code, "message": messages.get(code, messages["generation_failed"])}


def _spec_from_profile(profile: ModelProfile) -> GenerationAttemptSpec:
    connection = profile.connection
    dialect = (
        connection.dialect if connection else ModelConnection.Dialect.BUILTIN_OLLAMA
    )
    if dialect == ModelConnection.Dialect.BUILTIN_OLLAMA:
        provider = "ollama"
        server = settings.OLLAMA_BASE_URL
    elif dialect == ModelConnection.Dialect.OLLAMA_COMPATIBLE and connection:
        provider = "ollama_compatible"
        server = connection.endpoint_url
    else:
        provider = dialect
        server = ""
    snapshot = profile.snapshot()
    snapshot["provider"] = provider
    snapshot["base_url"] = server
    return GenerationAttemptSpec(
        provider=provider,
        model=profile.model_id,
        ollama_server=server,
        snapshot=snapshot,
    )


def _legacy_spec(run: GenerationRun) -> GenerationAttemptSpec:
    model = run.model_profile or settings.OLLAMA_MODEL
    return GenerationAttemptSpec(
        provider="ollama",
        model=model,
        ollama_server=settings.OLLAMA_BASE_URL,
        snapshot={
            "provider": "ollama",
            "base_url": settings.OLLAMA_BASE_URL,
            "profile": run.model_profile or "",
            "legacy": True,
        },
    )


def _attempt_specs(run: GenerationRun) -> tuple[GenerationAttemptSpec, ...]:
    try:
        selection: ModelSelection = resolve_model_selection(
            user=run.user,
            chat_override_profile_id=run.model_profile,
        )
    except ModelProfile.DoesNotExist:
        return (_legacy_spec(run),)
    return tuple(_spec_from_profile(profile) for profile in selection.attempts[:2])


def _messages_before_run(run: GenerationRun) -> list[dict[str, Any]]:
    recent_query = Message.objects.filter(chat=run.chat).order_by("created_at")
    if run.user_message_id is not None:
        recent_query = recent_query.exclude(pk=run.user_message_id)
    return [
        {"role": message.role, "content": message.content} for message in recent_query
    ]


def _generate_response(
    *,
    run: GenerationRun,
    spec: GenerationAttemptSpec,
    recent_messages: list[dict[str, Any]],
    available_scriptures: list[str],
) -> tuple[str, list[dict[str, Any]], str]:
    if spec.provider not in {"ollama", "ollama_compatible"} or not spec.ollama_server:
        raise RuntimeError("unsupported_provider_for_generation")
    engine = RAGEngine(
        vector_store=PgVectorStore(),
        ollama_model=spec.model,
        ollama_server=spec.ollama_server,
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
    return response_text, sources, mode


def _finish_cancelled(run: GenerationRun, attempt: GenerationAttempt) -> None:
    attempt.outcome = GenerationAttempt.Outcome.CANCELLED
    attempt.finished_at = timezone.now()
    attempt.save(update_fields=["outcome", "finished_at"])
    publish_run_event(run.stream_key, "state", {"state": run.state})


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

    recent_messages = _messages_before_run(run)
    available_scriptures = list(
        Scripture.objects.filter(is_indexed=True).values_list("name", flat=True)
    )
    specs = _attempt_specs(run)
    last_error_code = "generation_failed"

    for attempt_number, spec in enumerate(specs, start=1):
        attempt = GenerationAttempt.objects.create(
            run=run,
            attempt_number=attempt_number,
            provider=spec.provider,
            model=spec.model,
            model_snapshot=spec.snapshot,
        )

        try:
            response_text, sources, mode = _generate_response(
                run=run,
                spec=spec,
                recent_messages=recent_messages,
                available_scriptures=available_scriptures,
            )
            run.refresh_from_db(fields=["state"])
            if run.state == GenerationRun.State.CANCELLED:
                _finish_cancelled(run, attempt)
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
            return
        except Exception:
            logger.exception("Generation attempt failed for run %s", run_id)
            last_error_code = "generation_failed"
            attempt.outcome = GenerationAttempt.Outcome.FAILED
            attempt.error_code = last_error_code
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=["outcome", "error_code", "finished_at"])
            run.refresh_from_db(fields=["state"])
            if run.state == GenerationRun.State.CANCELLED:
                _finish_cancelled(run, attempt)
                return

    error_id = publish_run_event(
        run.stream_key, "error", _public_error(last_error_code)
    )
    publish_run_event(run.stream_key, "done", {"state": GenerationRun.State.FAILED})
    GenerationRun.objects.filter(pk=run.pk).update(
        state=GenerationRun.State.FAILED,
        error_code=last_error_code,
        last_event_id=error_id,
        finished_at=timezone.now(),
    )
