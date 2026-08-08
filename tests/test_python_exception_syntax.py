"""Regression tests for exception handling syntax."""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PY2_EXCEPT_RE = re.compile(r"^\s*except\s+[^(#\n]+,\s*[A-Za-z_]", re.MULTILINE)
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    "__pycache__",
    "frontend",
    "node_modules",
}


def test_python_code_uses_tuple_except_for_multiple_exceptions():
    offenders = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if any(
            part in EXCLUDED_PARTS or part.startswith(".venv") for part in path.parts
        ):
            continue
        text = path.read_text(encoding="utf-8")
        if PY2_EXCEPT_RE.search(text):
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []
