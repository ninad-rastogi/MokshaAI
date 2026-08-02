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


@pytest.mark.parametrize("context_length", ["100", "2000000"])
def test_model_scan_rejects_unsafe_context_range(context_length):
    assert main(["setup", "model", "scan", "--context-length", context_length]) == 2
