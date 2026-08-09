"""Unit tests for redacted logs and disk monitoring."""

import logging
from pathlib import Path

import yaml

from moksha.logging import JsonFormatter, redact
from moksha.tasks import disk_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _memory_to_mib(value: str) -> int:
    normalized = value.strip().lower()
    if normalized.endswith("g"):
        return int(normalized[:-1]) * 1024
    if normalized.endswith("m"):
        return int(normalized[:-1])
    raise AssertionError(f"unsupported memory unit: {value}")


def test_redact_removes_common_secret_shapes():
    rendered = redact("Authorization=Bearer-secret api_key=hidden sk-1234567890abcdef")

    assert "Bearer-secret" not in rendered
    assert "hidden" not in rendered
    assert "sk-1234567890abcdef" not in rendered


def test_json_formatter_omits_exception_message():
    formatter = JsonFormatter()
    try:
        raise RuntimeError("api_key=do-not-log")
    except RuntimeError:
        record = logging.LogRecord(
            "moksha.test",
            logging.ERROR,
            __file__,
            1,
            "operation failed",
            (),
            exc_info=None,
        )
        record.exc_info = __import__("sys").exc_info()

    rendered = formatter.format(record)
    assert "RuntimeError" in rendered
    assert "do-not-log" not in rendered


def test_disk_report_uses_configured_minimum(settings, tmp_path):
    settings.DISK_MIN_FREE_BYTES = 1

    report = disk_report([tmp_path])

    assert report[0]["path"] == str(tmp_path)
    assert report[0]["healthy"] is True


def test_compose_steady_memory_reservations_stay_below_target():
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]
    steady_reservations = [
        _memory_to_mib(service["mem_reservation"]) for service in services.values()
    ]

    assert sum(steady_reservations) <= 4096


def test_compose_publishes_only_caddy_edge_port():
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    published = {
        name: service.get("ports", [])
        for name, service in services.items()
        if service.get("ports")
    }

    assert published == {"caddy": ["${CADDY_HTTPS_PORT:-8443}:8443"]}


def test_compose_keeps_embedding_sidecar_private():
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    embedding = compose["services"]["embedding"]
    django = compose["services"]["django"]
    generation_worker = compose["services"]["generation-worker"]

    assert "ports" not in embedding
    assert (
        django["environment"].count("EMBEDDING_SERVICE_URL=http://embedding:8010") == 1
    )
    assert (
        generation_worker["environment"].count(
            "EMBEDDING_SERVICE_URL=http://embedding:8010"
        )
        == 1
    )


def test_product_service_images_use_non_root_users():
    django_dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    nuxt_dockerfile = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text()

    assert "USER moksha" in django_dockerfile
    assert "USER node" in nuxt_dockerfile


def test_compose_uses_dedicated_generation_and_installation_queues():
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert "-Q generation" in services["generation-worker"]["command"]
    assert "-Q model-installation" in services["model-installer"]["command"]
    assert "-Q generation" not in services["worker"]["command"]
    assert "-Q model-installation" not in services["worker"]["command"]


def test_caddy_routes_only_public_edge_contract():
    caddyfile = (PROJECT_ROOT / "deploy" / "Caddyfile").read_text()

    assert "handle /api/v1/* {\n\t\treverse_proxy django:8000\n\t}" in caddyfile
    assert "handle /admin/* {\n\t\treverse_proxy django:8000\n\t}" in caddyfile
    assert "handle /static/* {\n\t\treverse_proxy django:8000\n\t}" in caddyfile
    assert "handle {\n\t\treverse_proxy nuxt:3000\n\t}" in caddyfile
    assert "reverse_proxy embedding:" not in caddyfile
    assert "reverse_proxy redis:" not in caddyfile
    assert "reverse_proxy db:" not in caddyfile


def test_backup_script_excludes_runtime_secrets():
    backup_script = (PROJECT_ROOT / "scripts" / "backup.ps1").read_text()

    assert "excludes_secrets = $true" in backup_script
    assert "BYOK keyring is intentionally excluded" in backup_script
    assert "runtime-secrets" not in backup_script
    assert 'Join-Path $projectRoot "data"' in backup_script


def test_restore_script_requires_confirmation_and_pre_restore_backup():
    restore_script = (PROJECT_ROOT / "scripts" / "restore.ps1").read_text()

    assert "if (-not $ConfirmRestore)" in restore_script
    assert "Re-run with -ConfirmRestore" in restore_script
    assert 'backup.ps1") -Destination "backups/pre-restore"' in restore_script
    assert (
        "docker compose stop django worker generation-worker model-installer scheduler"
        in restore_script
    )
    assert (
        "docker compose start django worker generation-worker model-installer scheduler"
        in restore_script
    )
