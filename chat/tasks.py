"""Celery tasks for durable chat generation."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chat.citations import (
    citation_from_chunk,
    enforce_grounded_response,
    validate_citations,
)
from chat.events import publish_run_event
from chat.models import GenerationAttempt, GenerationRun, Message
from chat.rag.embeddings import PgVectorStore
from chat.rag.engine import RAGEngine
from llm.models import ModelConnection, ModelProfile
from llm.providers import (
    ProviderRequestFailed,
    ollama_chat_completion,
    openai_chat_completion,
)
from llm.services import ModelSelection, resolve_model_selection
from scriptures.models import Scripture

logger = logging.getLogger("chat.tasks")
FINAL_DELTA_CHARS = 180
REMOTE_BILLING_WARNING = (
    "A failed remote provider attempt may still be billed by that provider."
)


class GenerationCancelled(RuntimeError):
    """Stop provider streaming after an explicit user cancellation."""


@dataclass(frozen=True)
class GenerationAttemptSpec:
    """One concrete provider/model attempt for a run."""

    provider: str
    model: str
    ollama_server: str
    connection: ModelConnection | None
    temperature: float
    max_output_tokens: int
    snapshot: dict[str, Any]


def _public_error(code: str) -> dict[str, str]:
    messages = {
        "generation_cancelled": "This response was cancelled.",
        ModelConnection.Status.AUTH_INVALID: (
            "The selected provider rejected its credential. Check model settings."
        ),
        ModelConnection.Status.ENDPOINT_INVALID: (
            "The selected provider endpoint is not usable. Check model settings."
        ),
        ModelConnection.Status.MODEL_UNAVAILABLE: (
            "The selected provider does not have that model available."
        ),
        ModelConnection.Status.QUOTA_LIMITED: (
            "The selected provider reported an account quota limit."
        ),
        ModelConnection.Status.RATE_LIMITED: (
            "The selected provider is rate limited. Retry later or choose another model."
        ),
        ModelConnection.Status.UNREACHABLE: (
            "The selected provider could not be reached. Check model settings."
        ),
        ModelConnection.Status.DEGRADED: (
            "The selected provider is temporarily degraded. Retry later."
        ),
        "generation_failed": (
            "I could not complete that response. Please retry in a moment."
        ),
    }
    return {"code": code, "message": messages.get(code, messages["generation_failed"])}


def _error_code_from_exception(exc: Exception) -> str:
    if isinstance(exc, ProviderRequestFailed):
        return exc.code
    return "generation_failed"


def _remote_attempt_may_bill(spec: GenerationAttemptSpec) -> bool:
    return spec.provider in {
        ModelConnection.Dialect.OPENAI_COMPATIBLE,
        "ollama_compatible",
    }


def _emit_sanitized_deltas(
    text: str,
    on_delta: Callable[[str], None],
    *,
    chunk_size: int = FINAL_DELTA_CHARS,
) -> None:
    """Emit already-validated final text in bounded chunks."""
    if chunk_size < 1:
        raise ValueError("chunk_size_invalid")
    for start in range(0, len(text), chunk_size):
        on_delta(text[start : start + chunk_size])


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
        connection=connection,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        snapshot=snapshot,
    )


def _legacy_spec(run: GenerationRun) -> GenerationAttemptSpec:
    model = run.model_profile or settings.OLLAMA_MODEL
    return GenerationAttemptSpec(
        provider="ollama",
        model=model,
        ollama_server=settings.OLLAMA_BASE_URL,
        connection=None,
        temperature=0.7,
        max_output_tokens=1024,
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
    on_delta: Callable[[str], None],
) -> tuple[str, list[dict[str, Any]], str]:
    if spec.provider == ModelConnection.Dialect.OPENAI_COMPATIBLE:
        return _generate_remote_provider_response(
            completion_func=openai_chat_completion,
            run=run,
            spec=spec,
            recent_messages=recent_messages,
            available_scriptures=available_scriptures,
            on_delta=on_delta,
        )
    if spec.provider == "ollama_compatible":
        return _generate_remote_provider_response(
            completion_func=ollama_chat_completion,
            run=run,
            spec=spec,
            recent_messages=recent_messages,
            available_scriptures=available_scriptures,
            on_delta=on_delta,
        )
    if spec.provider != "ollama" or not spec.ollama_server:
        raise RuntimeError("unsupported_provider_for_generation")
    engine = RAGEngine(
        vector_store=PgVectorStore(),
        ollama_model=spec.model,
        ollama_server=spec.ollama_server,
        system_prompt=settings.SPIRITUAL_GUIDE_SYSTEM_PROMPT,
        available_scriptures=available_scriptures,
    )
    route, requires_scripture = engine.route_query(run.prompt)
    sources: list[dict[str, Any]]
    if route == "safety":
        response_text = engine.query_without_rag(
            run.prompt,
            recent_messages,
            on_delta=None,
        )
        sources = []
        mode = "SAFETY"
    elif route == "rag" and requires_scripture:
        response_text, sources = engine.query_with_rag(
            run.prompt,
            recent_messages,
            on_delta=None,
        )
        mode = "RAG"
    else:
        response_text = engine.query_without_rag(
            run.prompt,
            recent_messages,
            on_delta=None,
        )
        sources = []
        mode = "GENERAL"
    return enforce_grounded_response(response_text, sources), sources, mode


def _chat_history_messages(
    *,
    system_prompt: str,
    recent_messages: list[dict[str, Any]],
    prompt: str,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    for message in recent_messages[-6:]:
        role = message.get("role")
        content = str(message.get("content", ""))
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    return messages


def _generate_remote_provider_response(
    *,
    completion_func,
    run: GenerationRun,
    spec: GenerationAttemptSpec,
    recent_messages: list[dict[str, Any]],
    available_scriptures: list[str],
    on_delta: Callable[[str], None],
) -> tuple[str, list[dict[str, Any]], str]:
    if spec.connection is None:
        raise RuntimeError("provider_connection_missing")
    system_prompt = settings.SPIRITUAL_GUIDE_SYSTEM_PROMPT.format(
        available_scriptures=(
            ", ".join(available_scriptures)
            if available_scriptures
            else "None available"
        )
    )
    if not available_scriptures:
        prompt = (
            f"{run.prompt}\n\n"
            "Answer from general spiritual guidance only. If scripture evidence is "
            "needed, say that indexed evidence is unavailable."
        )
        response_text, usage = completion_func(
            connection=spec.connection,
            model=spec.model,
            messages=_chat_history_messages(
                system_prompt=system_prompt,
                recent_messages=recent_messages,
                prompt=prompt,
            ),
            temperature=spec.temperature,
            max_output_tokens=spec.max_output_tokens,
            on_delta=None,
        )
        spec.snapshot["reported_usage"] = usage
        return enforce_grounded_response(response_text, []), [], "GENERAL"

    engine = RAGEngine(
        vector_store=PgVectorStore(),
        ollama_model=settings.OLLAMA_MODEL,
        ollama_server=settings.OLLAMA_BASE_URL,
        system_prompt=settings.SPIRITUAL_GUIDE_SYSTEM_PROMPT,
        available_scriptures=available_scriptures,
    )
    route, requires_scripture = engine.route_query(run.prompt)
    if route == "safety":
        prompt = run.prompt
        mode = "SAFETY"
        sources: list[dict[str, Any]] = []
    elif route == "rag" and requires_scripture:
        chunks = engine.vector_store.search(
            run.prompt, top_k=3, allowed_scriptures=available_scriptures
        )
        chunks = [
            chunk for chunk in chunks if chunk["score"] >= settings.RAG_MIN_SIMILARITY
        ]
        if not chunks:
            no_evidence = (
                "I could not find a sufficiently relevant passage in the indexed "
                "scriptures to answer that reliably. Please try a more specific "
                "question or ask for general spiritual guidance."
            )
            on_delta(no_evidence)
            return no_evidence, [], "RAG"
        context_parts = []
        sources = []
        for index, chunk in enumerate(chunks):
            scripture = chunk.get("scripture", "Unknown")
            file_name = chunk.get("file_name", "Unknown")
            page = chunk.get("page", "N/A")
            context_parts.append(
                f"[Source {index + 1}: {scripture}, {file_name}, p. {page}]\n"
                f"{chunk['text']}\n"
            )
            sources.append(citation_from_chunk(chunk))
        prompt = (
            "Based ONLY on the following scripture context, answer the user's "
            f"question.\n\nScripture Context:\n{'\n'.join(context_parts)}\n\n"
            f"User Question: {run.prompt}\n\n"
            "Instructions:\n"
            "- Start with a section named 'Source verse' and include one exact "
            "quotation copied from the context.\n"
            "- If the exact quotation is Sanskrit or Devanagari, preserve it "
            "exactly and then translate it.\n"
            "- Add sections named 'Meaning' and 'Guidance'.\n"
            "- Cite every factual scripture claim inline as [Scripture, file, p. N].\n"
            "- Never cite, name, or invent a scripture, book, file, page, chapter, "
            "or verse that is not in the provided context source labels."
        )
        mode = "RAG"
    else:
        prompt = run.prompt
        mode = "GENERAL"
        sources = []

    response_text, usage = completion_func(
        connection=spec.connection,
        model=spec.model,
        messages=_chat_history_messages(
            system_prompt=system_prompt,
            recent_messages=recent_messages,
            prompt=prompt,
        ),
        temperature=spec.temperature,
        max_output_tokens=spec.max_output_tokens,
        on_delta=None,
    )
    spec.snapshot["reported_usage"] = usage
    return enforce_grounded_response(response_text, sources), sources, mode


def _finish_cancelled(
    run: GenerationRun,
    attempt: GenerationAttempt,
    partial_text: str = "",
) -> None:
    attempt.outcome = GenerationAttempt.Outcome.CANCELLED
    attempt.finished_at = timezone.now()
    attempt.save(update_fields=["outcome", "finished_at"])
    run.state = GenerationRun.State.CANCELLED
    state_id = publish_run_event(run.stream_key, "state", {"state": run.state})
    done_id = publish_run_event(run.stream_key, "done", {"state": run.state})
    update_values: dict[str, Any] = {
        "state": run.state,
        "last_event_id": done_id or state_id,
        "finished_at": timezone.now(),
    }
    if partial_text:
        update_values["final_text"] = partial_text
    GenerationRun.objects.filter(pk=run.pk).update(**update_values)


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
    warnings: list[str] = []

    for attempt_number, spec in enumerate(specs, start=1):
        attempt = GenerationAttempt.objects.create(
            run=run,
            attempt_number=attempt_number,
            provider=spec.provider,
            model=spec.model,
            model_snapshot=spec.snapshot,
        )

        emitted_any = False
        streamed_parts: list[str] = []
        last_delta_id = ""
        checkpoint_size = 0
        streamed_size = 0

        def on_delta(text: str, parts: list[str] = streamed_parts) -> None:
            nonlocal emitted_any, last_delta_id, checkpoint_size, streamed_size
            if not text:
                return
            if GenerationRun.objects.filter(
                pk=run.pk,
                state=GenerationRun.State.CANCELLED,
            ).exists():
                raise GenerationCancelled("generation_cancelled")
            emitted_any = True
            parts.append(text)
            streamed_size += len(text)
            last_delta_id = publish_run_event(
                run.stream_key,
                "delta",
                {"text": text},
            )
            if streamed_size - checkpoint_size >= 500:
                GenerationRun.objects.filter(pk=run.pk).update(
                    final_text="".join(parts),
                    last_event_id=last_delta_id,
                )
                checkpoint_size = streamed_size

        try:
            response_text, sources, mode = _generate_response(
                run=run,
                spec=spec,
                recent_messages=recent_messages,
                available_scriptures=available_scriptures,
                on_delta=on_delta,
            )
            sources = cast(list[dict[str, Any]], validate_citations(sources))
            response_text = enforce_grounded_response(response_text, sources)
            if not emitted_any and response_text:
                _emit_sanitized_deltas(response_text, on_delta)
            run.refresh_from_db(fields=["state"])
            if run.state == GenerationRun.State.CANCELLED:
                _finish_cancelled(run, attempt, "".join(streamed_parts))
                return

            assistant_message = Message.objects.create(
                chat=run.chat,
                role="assistant",
                content=response_text,
                mode=mode,
                sources=sources,
            )
            for source in sources:
                publish_run_event(run.stream_key, "citation", source)
            usage = spec.snapshot.get("reported_usage", {})
            usage_id = publish_run_event(
                run.stream_key,
                "usage",
                {
                    "attempt_number": attempt_number,
                    "provider": spec.provider,
                    "model": spec.model,
                    "usage": usage,
                    "warnings": warnings,
                },
            )
            done_id = publish_run_event(
                run.stream_key,
                "done",
                {
                    "state": GenerationRun.State.COMPLETED,
                    "message_id": assistant_message.pk,
                },
            )

            attempt.outcome = GenerationAttempt.Outcome.SUCCEEDED
            attempt.usage = usage
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=["outcome", "usage", "finished_at"])
            GenerationRun.objects.filter(pk=run.pk).update(
                state=GenerationRun.State.COMPLETED,
                assistant_message=assistant_message,
                final_text=response_text,
                final_sources=sources,
                last_event_id=done_id or usage_id or last_delta_id,
                finished_at=timezone.now(),
            )
            return
        except GenerationCancelled:
            run.refresh_from_db(fields=["state"])
            if run.state != GenerationRun.State.CANCELLED:
                GenerationRun.objects.filter(pk=run.pk).update(
                    state=GenerationRun.State.CANCELLED,
                    finished_at=timezone.now(),
                )
            _finish_cancelled(run, attempt, "".join(streamed_parts))
            return
        except Exception as exc:
            logger.exception("Generation attempt failed for run %s", run_id)
            last_error_code = _error_code_from_exception(exc)
            if (
                _remote_attempt_may_bill(spec)
                and REMOTE_BILLING_WARNING not in warnings
            ):
                warnings.append(REMOTE_BILLING_WARNING)
            attempt.outcome = GenerationAttempt.Outcome.FAILED
            attempt.error_code = last_error_code
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=["outcome", "error_code", "finished_at"])
            run.refresh_from_db(fields=["state"])
            if run.state == GenerationRun.State.CANCELLED:
                _finish_cancelled(run, attempt, "".join(streamed_parts))
                return
            if emitted_any:
                GenerationRun.objects.filter(pk=run.pk).update(
                    final_text="".join(streamed_parts),
                    last_event_id=last_delta_id,
                )
                break

    error_payload = _public_error(last_error_code)
    if warnings:
        error_payload["warning"] = REMOTE_BILLING_WARNING
    error_id = publish_run_event(run.stream_key, "error", error_payload)
    done_id = publish_run_event(
        run.stream_key, "done", {"state": GenerationRun.State.FAILED}
    )
    GenerationRun.objects.filter(pk=run.pk).update(
        state=GenerationRun.State.FAILED,
        error_code=last_error_code,
        last_event_id=done_id or error_id,
        finished_at=timezone.now(),
    )
