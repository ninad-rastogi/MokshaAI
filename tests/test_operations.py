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
