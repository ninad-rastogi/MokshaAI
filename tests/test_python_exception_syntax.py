"""Regression tests for exception handling syntax."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def test_project_python_files_compile_under_target_runtime():
    offenders = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if any(
            part in EXCLUDED_PARTS or part.startswith(".venv") for part in path.parts
        ):
            continue
        text = path.read_text(encoding="utf-8")
        try:
            compile(text, str(path), "exec")
        except SyntaxError as error:
            offenders.append(
                f"{path.relative_to(PROJECT_ROOT).as_posix()}:{error.lineno}"
            )

    assert offenders == []
