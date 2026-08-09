"""Tests for the opt-in README scaffold command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = PROJECT_ROOT / "scripts" / "scaffold_readme.py"
VALIDATOR = PROJECT_ROOT / "scripts" / "validate_readmes.py"


def _make_boundary(root: Path) -> Path:
    boundary = root / "domain"
    boundary.mkdir()
    (boundary / "alpha.py").write_text("VALUE = 1\n", encoding="utf-8")
    (boundary / "beta.py").write_text("VALUE = 2\n", encoding="utf-8")
    return boundary


def _write_valid_root_readme(root: Path) -> None:
    sections = (
        "Purpose",
        "Architecture And Data Flow",
        "Files And Entrypoints",
        "Interfaces",
        "Configuration",
        "Commands",
        "Tests",
        "Dependencies",
        "Security",
        "Failure Modes And Troubleshooting",
        "Related Docs",
    )
    body = "\n\n".join(f"## {section}\n\nTest documentation." for section in sections)
    (root / "README.md").write_text(
        f"<!-- moksha-readme-boundary:v1 -->\n# Test Project\n\n{body}\n",
        encoding="utf-8",
    )


def test_scaffold_creates_one_opt_in_boundary_readme(tmp_path: Path) -> None:
    boundary = _make_boundary(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCAFFOLD), "domain", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    readme = boundary / "README.md"
    assert result.returncode == 0
    assert "created domain/README.md" in result.stdout
    assert readme.is_file()
    assert "<!-- moksha-readme-boundary:v1 -->" in readme.read_text(encoding="utf-8")
    assert not (tmp_path / "README.md").exists()


def test_scaffold_refuses_to_overwrite_existing_readme(tmp_path: Path) -> None:
    boundary = _make_boundary(tmp_path)
    readme = boundary / "README.md"
    readme.write_text("existing\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCAFFOLD), "domain", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "README already exists" in result.stderr
    assert readme.read_text(encoding="utf-8") == "existing\n"


def test_scaffold_placeholders_fail_strict_validation(tmp_path: Path) -> None:
    _make_boundary(tmp_path)

    scaffold = subprocess.run(
        [sys.executable, str(SCAFFOLD), "domain", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    validation = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(tmp_path),
            "--warnings-as-errors",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert scaffold.returncode == 0
    assert validation.returncode == 1
    assert "placeholder text found" in validation.stdout


def test_validator_ignores_collected_staticfiles(tmp_path: Path) -> None:
    _write_valid_root_readme(tmp_path)
    generated = tmp_path / "staticfiles" / "admin" / "img"
    generated.mkdir(parents=True)
    (generated / "README.md").write_text("Generated asset notes.\n", encoding="utf-8")

    validation = subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert validation.returncode == 0
    assert "staticfiles" not in validation.stdout
