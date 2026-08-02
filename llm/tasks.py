"""Staff-only local model installation and qualification tasks."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from llm.models import (
    ModelConnection,
    ModelInstallationJob,
    ModelProfile,
)
from llm.security import validate_public_https_endpoint
from scripts.benchmark_ollama import (
    benchmark_model,
    build_cases,
    discover_collection_names,
)

logger = logging.getLogger("llm.tasks")

DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_REDIRECTS = 5
SAFE_TAG_RE = re.compile(r"[^a-z0-9._-]+")


class InstallationError(RuntimeError):
    """Stable local installation failure."""


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _validated_download_response(
    session: requests.Session,
    url: str,
    *,
    offset: int,
) -> requests.Response:
    current = url
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_https_endpoint(current)
        response = session.get(
            current,
            headers=headers,
            stream=True,
            allow_redirects=False,
            timeout=(10, 120),
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = response.headers.get("Location")
        response.close()
        if not location:
            raise InstallationError("model_download_redirect_invalid")
        current = urljoin(current, location)
        if urlparse(current).scheme != "https":
            raise InstallationError("model_download_redirect_invalid")
    raise InstallationError("model_download_too_many_redirects")


def _verify_file(path: Path, expected_size: int, expected_sha256: str) -> None:
    if path.stat().st_size != expected_size:
        raise InstallationError("model_source_size_mismatch")
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(DOWNLOAD_CHUNK_BYTES), b""):
            hasher.update(block)
    if hasher.hexdigest() != expected_sha256:
        raise InstallationError("model_source_hash_mismatch")


def _download_entry(entry: dict, imports_dir: Path) -> Path:
    imports_dir.mkdir(parents=True, exist_ok=True)
    final_path = (imports_dir / str(entry["file"])).resolve()
    if final_path.parent != imports_dir.resolve():
        raise InstallationError("model_source_path_invalid")
    part_path = final_path.with_suffix(final_path.suffix + ".part")
    expected_size = int(entry["size"])
    if part_path.exists() and part_path.stat().st_size > expected_size:
        part_path.unlink()
    offset = part_path.stat().st_size if part_path.exists() else 0
    session = _session()
    try:
        response = _validated_download_response(
            session,
            str(entry["download_url"]),
            offset=offset,
        )
        if response.status_code not in ({206} if offset else {200, 206}):
            raise InstallationError("model_download_http_failure")
        mode = "ab" if offset and response.status_code == 206 else "wb"
        written = offset if mode == "ab" else 0
        with part_path.open(mode) as output:
            for block in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                if not block:
                    continue
                written += len(block)
                if written > expected_size:
                    raise InstallationError("model_download_size_exceeded")
                output.write(block)
        response.close()
    except (OSError, requests.RequestException) as error:
        raise InstallationError("model_download_failed") from error
    finally:
        session.close()
    _verify_file(part_path, expected_size, str(entry["sha256"]))
    part_path.replace(final_path)
    return final_path


def _ollama_url(path: str) -> str:
    return f"{settings.OLLAMA_BASE_URL.rstrip('/')}{path}"


def _ollama_json(
    session: requests.Session,
    path: str,
    payload: dict,
    *,
    timeout: int = 300,
) -> dict:
    response = session.post(
        _ollama_url(path),
        json=payload,
        timeout=(10, timeout),
    )
    try:
        response.raise_for_status()
        value = response.json()
    except (requests.RequestException, requests.JSONDecodeError) as error:
        raise InstallationError("ollama_api_failure") from error
    finally:
        response.close()
    if not isinstance(value, dict):
        raise InstallationError("ollama_response_invalid")
    return value


def _copy_model(
    session: requests.Session,
    source: str,
    destination: str,
) -> None:
    response = session.post(
        _ollama_url("/api/copy"),
        json={"source": source, "destination": destination},
        timeout=(10, 120),
    )
    try:
        response.raise_for_status()
    except requests.RequestException as error:
        raise InstallationError("ollama_copy_failed") from error
    finally:
        response.close()


def _existing_models(session: requests.Session) -> set[str]:
    response = session.get(_ollama_url("/api/tags"), timeout=(10, 30))
    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, requests.JSONDecodeError) as error:
        raise InstallationError("ollama_tags_unavailable") from error
    finally:
        response.close()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    return {
        str(item.get("name"))
        for item in models
        if isinstance(item, dict) and item.get("name")
    }


def _upload_blob(session: requests.Session, source: Path, sha256: str) -> None:
    digest = f"sha256:{sha256}"
    head = session.head(_ollama_url(f"/api/blobs/{digest}"), timeout=(10, 30))
    try:
        if head.status_code == 200:
            return
        if head.status_code != 404:
            raise InstallationError("ollama_blob_probe_failed")
    finally:
        head.close()
    with source.open("rb") as model_file:
        response = session.post(
            _ollama_url(f"/api/blobs/{digest}"),
            data=model_file,
            headers={"Content-Length": str(source.stat().st_size)},
            timeout=(10, 3600),
        )
    try:
        if response.status_code != 201:
            raise InstallationError("ollama_blob_upload_failed")
    finally:
        response.close()


def _create_model(
    session: requests.Session,
    tag: str,
    entry: dict,
) -> None:
    ollama = entry["ollama"]
    response = session.post(
        _ollama_url("/api/create"),
        json={
            "model": tag,
            "files": {
                entry["file"]: f"sha256:{entry['sha256']}",
            },
            "license": entry["license"],
            "parameters": {
                "num_ctx": ollama["num_ctx"],
                "num_predict": ollama["num_predict"],
                "temperature": ollama["temperature"],
            },
            "stream": False,
        },
        timeout=(10, 900),
    )
    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, requests.JSONDecodeError) as error:
        raise InstallationError("ollama_create_failed") from error
    finally:
        response.close()
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise InstallationError("ollama_create_failed")


def _delete_model(session: requests.Session, tag: str) -> None:
    try:
        response = session.delete(
            _ollama_url("/api/delete"),
            json={"model": tag},
            timeout=(10, 60),
        )
        response.close()
    except requests.RequestException:
        logger.warning("Temporary Ollama tag cleanup failed")


def _qualified_tag(entry: dict, catalog_version: str) -> str:
    base = SAFE_TAG_RE.sub("-", str(entry["id"]).lower()).strip("-")
    version = SAFE_TAG_RE.sub("-", catalog_version.lower()).strip("-")
    return f"moksha-{base}:{version}"


def _qualify(tag: str) -> dict:
    collections = discover_collection_names(Path(settings.DOCS_DIR))
    report = benchmark_model(
        settings.OLLAMA_BASE_URL,
        tag,
        runs=1,
        timeout=float(settings.OLLAMA_TIMEOUT_SECONDS),
        cases=build_cases(collections),
    )
    passed = (
        report["pass_rate"] == 1.0
        and report["minimum_tokens_per_second"] >= settings.MODEL_MIN_TOKENS_PER_SECOND
    )
    if not passed:
        raise InstallationError("model_qualification_failed")
    memory = _running_model_memory(tag)
    if memory["size_vram"] > settings.MODEL_MAX_VRAM_BYTES:
        raise InstallationError("model_vram_limit_exceeded")
    report["memory"] = memory
    return report


def _running_model_memory(tag: str) -> dict[str, int]:
    session = _session()
    try:
        response = session.get(_ollama_url("/api/ps"), timeout=(10, 30))
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, requests.JSONDecodeError) as error:
        raise InstallationError("ollama_memory_probe_failed") from error
    finally:
        session.close()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    for item in models:
        if not isinstance(item, dict):
            continue
        names = {str(item.get("name", "")), str(item.get("model", ""))}
        if tag in names:
            return {
                "size": int(item.get("size") or 0),
                "size_vram": int(item.get("size_vram") or 0),
                "configured_max_vram": int(settings.MODEL_MAX_VRAM_BYTES),
            }
    raise InstallationError("ollama_memory_probe_model_missing")


@shared_task(bind=True, queue="model-installation")
def install_local_model(self, job_id: str) -> None:
    job = ModelInstallationJob.objects.select_related("created_by").get(pk=job_id)
    if job.status == ModelInstallationJob.Status.CANCELLED:
        return
    entry = job.catalog_entry
    catalog_version = str(entry.get("_catalog_version", "unknown"))
    final_tag = _qualified_tag(entry, catalog_version)
    temp_tag = f"{final_tag}-candidate-{str(job.pk)[:8]}"
    imports_dir = Path(settings.OLLAMA_IMPORTS_DIR).resolve()
    source_path: Path | None = None
    final_created = False
    session = _session()
    ModelInstallationJob.objects.filter(pk=job.pk).update(
        status=ModelInstallationJob.Status.RUNNING,
        started_at=timezone.now(),
        ollama_tag=temp_tag,
    )
    try:
        if final_tag in _existing_models(session):
            raise InstallationError("model_tag_already_exists")
        source_path = _download_entry(entry, imports_dir)
        ModelInstallationJob.objects.filter(pk=job.pk).update(
            import_path=str(source_path)
        )
        _upload_blob(session, source_path, job.source_sha256)
        _create_model(session, temp_tag, entry)
        qualification = _qualify(temp_tag)
        _copy_model(session, temp_tag, final_tag)
        final_created = True
        with transaction.atomic():
            connection, _ = ModelConnection.objects.get_or_create(
                user=None,
                name="Built-in Ollama",
                defaults={
                    "dialect": ModelConnection.Dialect.BUILTIN_OLLAMA,
                    "status": ModelConnection.Status.CONNECTED,
                },
            )
            profile = ModelProfile.objects.create(
                name=f"{entry['id']} {catalog_version}",
                connection=connection,
                model_id=final_tag,
                is_enabled=True,
                is_admin_default=False,
                context_window=int(entry["ollama"]["num_ctx"]),
                max_output_tokens=int(entry["ollama"]["num_predict"]),
                temperature=float(entry["ollama"]["temperature"]),
                concurrency_limit=1,
                qualification=qualification,
            )
            ModelInstallationJob.objects.filter(pk=job.pk).update(
                model_profile=profile,
                status=ModelInstallationJob.Status.SUCCEEDED,
                ollama_tag=final_tag,
                qualification=qualification,
                error_code="",
                finished_at=timezone.now(),
                active_lock=False,
            )
    except (InstallationError, OSError, ValueError, KeyError) as error:
        logger.exception("Local model installation failed for job %s", job_id)
        error_code = (
            str(error)
            if isinstance(error, InstallationError)
            else "model_installation_failed"
        )
        ModelInstallationJob.objects.filter(pk=job.pk).update(
            status=ModelInstallationJob.Status.FAILED,
            error_code=error_code,
            finished_at=timezone.now(),
            active_lock=False,
        )
        if final_created:
            _delete_model(session, final_tag)
        raise
    finally:
        _delete_model(session, temp_tag)
        session.close()
        part_path = imports_dir / f"{entry.get('file', 'model.gguf')}.part"
        part_path.unlink(missing_ok=True)
        if source_path and source_path.exists() and not job.keep_source:
            source_path.unlink(missing_ok=True)
