import builtins
from unittest.mock import patch

import pytest

from moksha.cli import build_parser, main


def test_model_scan_command_parses():
    args = build_parser().parse_args(
        ["setup", "model", "scan", "--top", "4", "--context-length", "8192"]
    )

    assert args.model_command == "scan"
    assert args.top == 4
    assert args.context_length == 8192


def test_model_scan_rejects_non_windows_host():
    with patch("moksha.cli.sys.platform", "linux"):
        assert main(["setup", "model", "scan"]) == 2


def test_model_scan_does_not_import_whichllm_on_non_windows_host():
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("whichllm"):
            raise AssertionError("whichllm_must_not_import_outside_windows_scan")
        return real_import(name, *args, **kwargs)

    with (
        patch("moksha.cli.sys.platform", "linux"),
        patch("builtins.__import__", side_effect=guarded_import),
    ):
        assert main(["setup", "model", "scan"]) == 2


@pytest.mark.parametrize("context_length", ["100", "2000000"])
def test_model_scan_rejects_unsafe_context_range(context_length):
    assert main(["setup", "model", "scan", "--context-length", context_length]) == 2
