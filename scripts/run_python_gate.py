"""Run a project command with the configured Python environment."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def configured_python(root: Path) -> Path:
    """Prefer an active environment, then a shared ancestor `.env`."""
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        candidate = Path(virtual_env) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        if candidate.is_file():
            return candidate

    executable = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    for parent in (root, *root.parents):
        candidate = parent / ".env" / executable
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: run_python_gate.py <python arguments>", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    command = [str(configured_python(root)), *sys.argv[1:]]
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
