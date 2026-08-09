"""Run frontend package gates from the repository root.

Pre-commit invokes this with system Python; npm uses the checked-in frontend
lockfile and node_modules.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ALLOWED_COMMANDS = {"format", "lint", "test", "typecheck", "build"}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS))
        print(f"Usage: run_frontend_gate.py <{allowed}>", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    npm = "npm.cmd" if os.name == "nt" else "npm"
    command = [npm, "run", sys.argv[1]]
    return subprocess.run(command, cwd=root / "frontend", check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
