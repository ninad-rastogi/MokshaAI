"""Create one opt-in boundary README after validating its target directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from validate_readmes import (
    CONTRACT_MARKER,
    README_NAME,
    directory_is_data_only,
    is_excluded,
    is_meaningful_boundary,
)

TEMPLATE = """{marker}
# {title}

## Purpose

<Describe why this boundary exists and what it owns.>

## Architecture And Data Flow

<Describe inputs, outputs, state, and important control flow.>

## Files And Entrypoints

<List important files, processes, and entrypoints.>

## Interfaces

<Document APIs, commands, queues, files, or other contracts.>

## Configuration

<List environment variables, settings, defaults, and secrets.>

## Commands

<List setup, development, and operational commands.>

## Tests

<Explain test locations and focused test commands.>

## Dependencies

<List important runtime, build, and external dependencies.>

## Security

<Document trust boundaries, sensitive data, and required safeguards.>

## Failure Modes And Troubleshooting

<List expected failures, diagnostics, and recovery steps.>

## Related Docs

<Link to parent, child, architecture, and operational documentation.>
"""


def _title_for(target: Path, root: Path) -> str:
    relative = target.relative_to(root)
    return f"{relative.as_posix()}/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly create one README.md for an existing architectural boundary. "
            "This command is interactive tooling; hooks and CI never run it."
        ),
    )
    parser.add_argument(
        "target",
        type=Path,
        help="opt-in target directory, relative to --root or absolute",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: parent of scripts/)",
    )
    return parser


def _resolve_target(raw_target: Path, root: Path) -> Path:
    return (raw_target if raw_target.is_absolute() else root / raw_target).resolve()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root.resolve()
    target = _resolve_target(args.target, root)

    if not root.is_dir():
        print(f"error: repository root is not a directory: {root}", file=sys.stderr)
        return 2
    try:
        relative = target.relative_to(root)
    except ValueError:
        print("error: target must remain inside the repository root", file=sys.stderr)
        return 2
    if not relative.parts:
        print(
            "error: target must be an opt-in subdirectory, not the root",
            file=sys.stderr,
        )
        return 2
    if not target.is_dir():
        print("error: target must be an existing directory", file=sys.stderr)
        return 2
    if target.is_symlink():
        print("error: symbolic-link targets are not supported", file=sys.stderr)
        return 2
    if is_excluded(target, root):
        print("error: target is excluded from README boundary policy", file=sys.stderr)
        return 2
    if directory_is_data_only(target):
        print(
            "error: data-only and fixture folders are not README boundaries",
            file=sys.stderr,
        )
        return 2
    if not is_meaningful_boundary(target, root):
        print(
            "error: target is trivial; choose a deployable service, app, or major subsystem",
            file=sys.stderr,
        )
        return 2

    readme = target / README_NAME
    if readme.exists():
        print(f"error: README already exists: {readme}", file=sys.stderr)
        return 2

    readme.write_text(
        TEMPLATE.format(marker=CONTRACT_MARKER, title=_title_for(target, root)),
        encoding="utf-8",
        newline="\n",
    )
    print(f"created {readme.relative_to(root).as_posix()}")
    print("replace every scaffold placeholder, then run scripts/validate_readmes.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
