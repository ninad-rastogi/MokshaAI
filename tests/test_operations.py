"""Unit tests for redacted logs and disk monitoring."""

import logging

from moksha.logging import JsonFormatter, redact
from moksha.tasks import disk_report


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
