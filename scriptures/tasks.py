"""Celery tasks for safe, auditable scripture indexing."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID

import fitz
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Greatest
from django.utils import timezone

from chat.models import DocumentChunk
from chat.rag.embeddings import EmbeddingServiceError, PgVectorStore
from chat.rag.loader import ScriptureDocumentLoader
from chat.rag.ocr import OcrUnavailableError, configured_ocr_engine
from scriptures.models import (
    IndexingJob,
    ScriptureIndexVersion,
    Volume,
)

logger = logging.getLogger("scriptures.tasks")

INDEX_FAILURE_BUILD = "index_build_failed"
INDEX_FAILURE_QUALIFICATION = "index_qualification_failed"
INDEX_FAILURE_SOURCE_TEXT = "index_source_text_corrupt"
INDEX_FAILURE_OCR_UNAVAILABLE = "index_ocr_unavailable"
INDEX_FAILURE_OCR_QUALITY = "index_ocr_quality_failed"

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
SUSPICIOUS_LATIN_RE = re.compile(r"[\u0080-\u024F]")
MAX_SUSPICIOUS_SOURCE_RATIO = 0.05


def source_text_quality(chunks: list[dict[str, Any]]) -> dict[str, int | float | bool]:
    """Measure extraction corruption in Devanagari-bearing source chunks."""
    source_chunks = [
        str(chunk.get("text", ""))
        for chunk in chunks
        if DEVANAGARI_RE.search(str(chunk.get("text", "")))
    ]
    suspicious_chunks = sum(
        bool(SUSPICIOUS_LATIN_RE.search(text)) for text in source_chunks
    )
    suspicious_ratio = suspicious_chunks / len(source_chunks) if source_chunks else 0.0
    return {
        "devanagari_chunks": len(source_chunks),
        "suspicious_source_chunks": suspicious_chunks,
        "suspicious_source_ratio": round(suspicious_ratio, 4),
        "max_suspicious_source_ratio": MAX_SUSPICIOUS_SOURCE_RATIO,
        "source_text_qualified": suspicious_ratio <= MAX_SUSPICIOUS_SOURCE_RATIO,
    }


def record_embedding_progress(job_id: int, completed: int, total: int) -> None:
    """Persist bounded candidate-build progress after each committed batch."""
    fraction = completed / total if total else 0
    progress = 70 + min(14, int(fraction * 14))
    IndexingJob.objects.filter(pk=job_id).update(
        progress=Greatest("progress", Value(progress)),
        chunks_indexed=completed,
        heartbeat_at=timezone.now(),
    )


def candidate_checkpoint(version_id: UUID, total_chunks: int) -> int:
    """Return resumable committed count, rejecting an impossible checkpoint."""
    persisted = DocumentChunk.objects.filter(index_version=version_id).count()
    if persisted > total_chunks:
        raise RuntimeError("index_checkpoint_invalid")
    return persisted


def candidate_can_retry(error: Exception, retries: int, max_retries: int) -> bool:
    """Return whether a transient dependency failure keeps the candidate resumable."""
    return isinstance(error, OSError | EmbeddingServiceError) and retries < max_retries


def index_progress_floor(current: int, resuming: bool) -> int:
    """Keep resumed candidate progress monotonic while sources are revalidated."""
    return max(current, 70) if resuming else 5


def ocr_page_progress(completed_pages: int, total_pages: int) -> int:
    """Expose live OCR page progress before embedding begins."""
    if total_pages <= 0:
        return 1
    percentage = round(completed_pages / total_pages * 100)
    return max(1, min(69, percentage))


def ocr_resume_completed_pages(reported_pages: int, checkpoint_pages: int) -> int:
    """Keep OCR resume display monotonic while cached pages are replayed."""
    return max(reported_pages, checkpoint_pages)


def monotonic_progress(current_progress: int, proposed_progress: int) -> int:
    """Never move visible indexing progress backward."""
    return max(current_progress, proposed_progress)


def record_ocr_progress(
    job_id: int,
    completed_pages: int,
    total_pages: int,
    *,
    checkpoint_pages: int = 0,
    volumes_processed: int | None = None,
) -> None:
    """Persist page-based OCR progress, even when resuming from a stale floor."""
    progress = ocr_page_progress(completed_pages, total_pages)
    updates: dict[str, object] = {
        "progress": Greatest("progress", Value(progress)),
        "chunks_indexed": Greatest("chunks_indexed", Value(completed_pages)),
        "ocr_pages_processed": Greatest("ocr_pages_processed", Value(completed_pages)),
        "ocr_checkpoint_pages": Greatest(
            "ocr_checkpoint_pages", Value(checkpoint_pages)
        ),
        "error_message": "ocr_fallback_running",
        "heartbeat_at": timezone.now(),
    }
    if volumes_processed is not None:
        updates["volumes_processed"] = volumes_processed
    IndexingJob.objects.filter(pk=job_id).update(**updates)


def compute_file_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


@shared_task(
    bind=True,
    autoretry_for=(OSError, EmbeddingServiceError),
    retry_backoff=True,
    max_retries=3,
)
def index_scripture(self, job_id: int) -> None:
    """Build a new scripture index before atomically removing stale chunks."""
    job = IndexingJob.objects.select_related("scripture").get(pk=job_id)
    scripture = job.scripture
    version = job.index_version
    resuming = (
        version is not None and version.status == ScriptureIndexVersion.Status.BUILDING
    )
    if not resuming:
        version = ScriptureIndexVersion.objects.create(
            scripture=scripture,
            embedding_model=settings.EMBEDDING_MODEL,
        )
    assert version is not None
    progress_floor = (
        max(job.progress, 8)
        if resuming and job.error_message == "ocr_fallback_running"
        else index_progress_floor(job.progress, resuming)
    )
    job_updates: dict[str, object] = {
        "status": IndexingJob.Status.RUNNING,
        "progress": progress_floor,
        "celery_task_id": self.request.id or "",
        "index_version": version,
        "error_message": "",
    }
    if job.started_at is None:
        job_updates["started_at"] = timezone.now()
    job_updates["heartbeat_at"] = timezone.now()
    IndexingJob.objects.filter(pk=job.pk).update(
        **job_updates,
    )
    try:
        scripture_path = Path(scripture.folder_path)
        loader = ScriptureDocumentLoader()
        pdf_files = loader._pdf_files(scripture_path)
        if not pdf_files:
            raise FileNotFoundError(f"No PDFs found for {scripture.name}")

        chunks = []
        volumes = []
        for number, pdf_path in enumerate(pdf_files, start=1):
            stat = pdf_path.stat()
            with fitz.open(str(pdf_path)) as pdf:
                page_count = len(pdf)
            volumes.append((pdf_path, stat, page_count, compute_file_hash(pdf_path)))
            chunks.extend(loader._load_pdf(pdf_path, scripture.name, scripture_path))
            IndexingJob.objects.filter(pk=job.pk).update(
                progress=Greatest(
                    "progress",
                    Value(
                        max(
                            progress_floor,
                            min(70, 5 + int(number / len(pdf_files) * 65)),
                        )
                    ),
                ),
                heartbeat_at=timezone.now(),
            )
        if not chunks:
            raise ValueError("No extractable text was found in the PDFs.")

        source_manifest = [
            {
                "file_name": loader._display_file_name(pdf_path, scripture_path),
                "sha256": content_hash,
                "size": stat.st_size,
                "pages": page_count,
            }
            for pdf_path, stat, page_count, content_hash in volumes
        ]
        if version.source_manifest and version.source_manifest != source_manifest:
            raise RuntimeError("index_source_changed_during_resume")
        version.source_manifest = source_manifest
        version.volume_count = len(volumes)
        version.page_count = sum(volume[2] for volume in volumes)
        version.save(
            update_fields=[
                "source_manifest",
                "volume_count",
                "page_count",
            ]
        )
        text_quality = source_text_quality(chunks)
        qualification_context: dict[str, Any] = {"source_text": text_quality}
        if not text_quality["source_text_qualified"]:
            if not settings.SCRIPTURE_OCR_ENABLED:
                raise RuntimeError(INDEX_FAILURE_SOURCE_TEXT)
            try:
                ocr_engine = configured_ocr_engine()
                if ocr_engine is None:
                    raise OcrUnavailableError("ocr_disabled")
                ocr_engine.assert_available()
                ocr_checkpoint_pages = job.chunks_indexed if resuming else 0
                record_ocr_progress(
                    job.pk,
                    0,
                    version.page_count or sum(volume[2] for volume in volumes),
                    checkpoint_pages=ocr_checkpoint_pages,
                )
                ocr_chunks = []
                total_ocr_pages = sum(volume[2] for volume in volumes)
                pages_before_volume = 0
                for number, pdf_path in enumerate(pdf_files, start=1):

                    def record_volume_ocr_progress(
                        page_number: int,
                        _pages: int,
                        *,
                        pages_before: int = pages_before_volume,
                        volume_number: int = number,
                    ) -> None:
                        completed_pages = pages_before + page_number
                        record_ocr_progress(
                            job.pk,
                            completed_pages,
                            total_ocr_pages,
                            checkpoint_pages=ocr_checkpoint_pages,
                            volumes_processed=volume_number - 1,
                        )

                    ocr_chunks.extend(
                        loader._load_pdf(
                            pdf_path,
                            scripture.name,
                            scripture_path,
                            force_ocr=True,
                            progress_callback=record_volume_ocr_progress,
                        )
                    )
                    pages_before_volume += volumes[number - 1][2]
                    record_ocr_progress(
                        job.pk,
                        pages_before_volume,
                        total_ocr_pages,
                        checkpoint_pages=ocr_checkpoint_pages,
                        volumes_processed=number,
                    )
            except OcrUnavailableError as exc:
                raise RuntimeError(INDEX_FAILURE_OCR_UNAVAILABLE) from exc
            chunks = ocr_chunks
            if not chunks:
                raise RuntimeError(INDEX_FAILURE_OCR_QUALITY)
            text_quality = source_text_quality(chunks)
            qualification_context = {
                "source_text": text_quality,
                "ocr": {
                    "engine": ocr_engine.name,
                    "languages": ocr_engine.languages,
                    "dpi": settings.SCRIPTURE_OCR_DPI,
                },
            }
            if not text_quality["source_text_qualified"]:
                raise RuntimeError(INDEX_FAILURE_OCR_QUALITY)
        version.qualification = qualification_context
        version.save(
            update_fields=[
                "source_manifest",
                "volume_count",
                "page_count",
                "qualification",
            ]
        )
        IndexingJob.objects.filter(pk=job.pk).update(
            volumes_processed=len(volumes),
            chunks_indexed=0,
            error_message="",
            heartbeat_at=timezone.now(),
        )

        # Write candidate first. Existing active retrieval remains available.
        vector_store = PgVectorStore()
        persisted = candidate_checkpoint(version.pk, len(chunks))
        if persisted:
            record_embedding_progress(job.pk, persisted, len(chunks))
        added = persisted + vector_store.add_chunks(
            chunks[persisted:],
            index_version=version.pk,
            progress_callback=lambda completed, _remaining: record_embedding_progress(
                job.pk,
                persisted + completed,
                len(chunks),
            ),
        )
        IndexingJob.objects.filter(pk=job.pk).update(
            progress=Greatest("progress", Value(85)),
            heartbeat_at=timezone.now(),
        )
        smoke_query = str(chunks[0]["text"])[:500]
        smoke_results = vector_store.search(
            smoke_query,
            top_k=1,
            scripture_filter=scripture.name,
            index_versions=[version.pk],
        )
        qualified = (
            added == len(chunks)
            and added > 0
            and len(source_manifest) == len(pdf_files)
            and bool(smoke_results)
            and smoke_results[0]["score"] >= settings.RAG_MIN_SIMILARITY
        )
        qualification = {
            **qualification_context,
            "expected_chunks": len(chunks),
            "stored_chunks": added,
            "volume_count": len(source_manifest),
            "retrieval_smoke": bool(smoke_results),
            "retrieval_score": smoke_results[0]["score"] if smoke_results else 0.0,
            "threshold": settings.RAG_MIN_SIMILARITY,
        }
        if not qualified:
            version.status = ScriptureIndexVersion.Status.FAILED
            version.failure_code = INDEX_FAILURE_QUALIFICATION
            version.qualification = qualification
            version.save(update_fields=["status", "failure_code", "qualification"])
            raise RuntimeError(INDEX_FAILURE_QUALIFICATION)
        version.status = ScriptureIndexVersion.Status.QUALIFIED
        version.chunk_count = added
        version.qualification = qualification
        version.qualified_at = timezone.now()
        version.save(
            update_fields=[
                "status",
                "chunk_count",
                "qualification",
                "qualified_at",
            ]
        )

        with transaction.atomic():
            for pdf_path, stat, page_count, content_hash in volumes:
                Volume.objects.update_or_create(
                    scripture=scripture,
                    file_name=loader._display_file_name(pdf_path, scripture_path),
                    defaults={
                        "file_path": str(pdf_path),
                        "file_size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "page_count": page_count,
                        "content_hash": content_hash,
                    },
                )
            previous_version_id = scripture.active_index_version_id
            if previous_version_id:
                ScriptureIndexVersion.objects.filter(
                    pk=previous_version_id,
                    status=ScriptureIndexVersion.Status.ACTIVE,
                ).update(status=ScriptureIndexVersion.Status.RETIRED)
            version.status = ScriptureIndexVersion.Status.ACTIVE
            version.activated_at = timezone.now()
            version.save(update_fields=["status", "activated_at"])
            scripture.total_volumes = len(volumes)
            scripture.total_pages = sum(volume[2] for volume in volumes)
            scripture.is_indexed = True
            scripture.last_indexed_at = timezone.now()
            scripture.active_index_version = version
            scripture.save(
                update_fields=[
                    "total_volumes",
                    "total_pages",
                    "is_indexed",
                    "last_indexed_at",
                    "active_index_version",
                ]
            )
            IndexingJob.objects.filter(pk=job.pk).update(
                status=IndexingJob.Status.SUCCEEDED,
                progress=100,
                chunks_indexed=added,
                volumes_processed=len(volumes),
                finished_at=timezone.now(),
                error_message="",
                heartbeat_at=timezone.now(),
            )
        retained_previous_ids = list(
            ScriptureIndexVersion.objects.filter(
                scripture=scripture,
                status=ScriptureIndexVersion.Status.RETIRED,
            )
            .order_by("-activated_at")
            .values_list("pk", flat=True)[:1]
        )
        stale_versions = ScriptureIndexVersion.objects.filter(
            scripture=scripture,
            status=ScriptureIndexVersion.Status.RETIRED,
        ).exclude(pk__in=retained_previous_ids)
        stale_ids = list(stale_versions.values_list("pk", flat=True))
        if stale_ids:
            DocumentChunk.objects.filter(index_version__in=stale_ids).delete()
            stale_versions.delete()
    except Exception as exc:
        logger.exception("Scripture indexing failed for job %s", job_id)
        if candidate_can_retry(
            exc,
            self.request.retries,
            self.max_retries or 0,
        ):
            IndexingJob.objects.filter(pk=job.pk).update(
                error_message="index_retry_pending",
                heartbeat_at=timezone.now(),
            )
            raise
        failure_code = {
            INDEX_FAILURE_QUALIFICATION: INDEX_FAILURE_QUALIFICATION,
            INDEX_FAILURE_SOURCE_TEXT: INDEX_FAILURE_SOURCE_TEXT,
            INDEX_FAILURE_OCR_UNAVAILABLE: INDEX_FAILURE_OCR_UNAVAILABLE,
            INDEX_FAILURE_OCR_QUALITY: INDEX_FAILURE_OCR_QUALITY,
        }.get(str(exc), INDEX_FAILURE_BUILD)
        ScriptureIndexVersion.objects.filter(
            pk=version.pk,
            status__in=[
                ScriptureIndexVersion.Status.BUILDING,
                ScriptureIndexVersion.Status.QUALIFIED,
            ],
        ).update(
            status=ScriptureIndexVersion.Status.FAILED,
            failure_code=failure_code,
        )
        IndexingJob.objects.filter(pk=job.pk).update(
            status=IndexingJob.Status.FAILED,
            error_message=failure_code,
            finished_at=timezone.now(),
            heartbeat_at=timezone.now(),
        )
        DocumentChunk.objects.filter(index_version=version.pk).delete()
        raise
