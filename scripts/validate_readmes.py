"""Validate README coverage and quality without changing the repository."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import unquote

CONTRACT_MARKER = "<!-- moksha-readme-boundary:v1 -->"
README_NAME = "README.md"

EXCLUDED_NAMES = frozenset(
    {
        ".benchmarks",
        ".git",
        ".mypy_cache",
        ".npm-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".tmp",
        "__pycache__",
        "assets",
        "cache",
        "caches",
        "coverage",
        "data",
        "fixtures",
        "generated",
        "graphify-out",
        "htmlcov",
        "images",
        "migrations",
        "node_modules",
        "public",
        "static",
        "test-results",
        "venv",
    }
)
EXCLUDED_SUFFIXES = (".egg-info",)
VIRTUALENV_MARKERS = ("pyvenv.cfg", "Scripts/activate", "bin/activate")

KNOWN_BOUNDARIES = frozenset(
    {
        "deploy",
        "docs",
        "embedding_service",
        "frontend",
        "operations",
        "scripts",
        "streamlit_ui",
        "tests",
    }
)
SUPPORT_BOUNDARIES = frozenset({"deploy", "docs", "operations", "scripts", "tests"})
NESTED_NON_BOUNDARIES = frozenset(
    {"commands", "components", "management", "test", "tests"}
)
BOUNDARY_FILES = frozenset(
    {
        "apps.py",
        "asgi.py",
        "Caddyfile",
        "main.py",
        "package.json",
        "settings.py",
        "wsgi.py",
    }
)
SOURCE_SUFFIXES = frozenset(
    {
        ".c",
        ".cpp",
        ".cs",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".php",
        ".py",
        ".rs",
        ".ts",
        ".tsx",
        ".vue",
    }
)
DATA_ONLY_SUFFIXES = frozenset(
    {
        ".csv",
        ".json",
        ".jsonl",
        ".parquet",
        ".pdf",
        ".sql",
        ".tsv",
        ".xml",
        ".yaml",
        ".yml",
    }
)

REQUIRED_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Purpose", ("purpose", "overview")),
    (
        "Architecture And Data Flow",
        ("architecture and data flow", "architecture", "data flow", "ui flow"),
    ),
    (
        "Files And Entrypoints",
        (
            "files and entrypoints",
            "files",
            "entrypoints",
            "entry points",
            "project structure",
        ),
    ),
    ("Interfaces", ("interfaces", "api", "api endpoints")),
    (
        "Configuration",
        ("configuration", "key configuration", "settings", "environment"),
    ),
    (
        "Commands",
        ("commands", "running", "quick start", "development workflow", "code quality"),
    ),
    ("Tests", ("tests", "testing", "running tests")),
    ("Dependencies", ("dependencies", "prerequisites")),
    ("Security", ("security", "security notes", "authentication", "safety")),
    (
        "Failure Modes And Troubleshooting",
        (
            "failure modes and troubleshooting",
            "failure modes",
            "troubleshooting",
            "errors",
        ),
    ),
    (
        "Related Docs",
        ("related docs", "project structure and documentation", "subdirectories"),
    ),
)

PLACEHOLDER_PATTERNS = (
    re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:coming soon|to be created|write this|fill (?:this|in))\b", re.IGNORECASE
    ),
    re.compile(r"<(?:describe|replace|insert|add)[^>]*>", re.IGNORECASE),
    re.compile(r"\[(?:describe|replace|insert|add)[^\]]*\]", re.IGNORECASE),
)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z &/-]{2,50}):", re.MULTILINE)
FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)\n]+)\)")
REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]]+]:\s*(\S+)", re.MULTILINE)


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    code: str
    path: Path
    message: str


def is_excluded(path: Path, root: Path) -> bool:
    """Return whether path belongs to a folder excluded from README policy."""
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True

    for part in relative.parts:
        lowered = part.casefold()
        if (
            lowered in EXCLUDED_NAMES
            or lowered.startswith(".venv")
            or lowered.endswith(EXCLUDED_SUFFIXES)
        ):
            return True
    return any((path / marker).exists() for marker in VIRTUALENV_MARKERS)


def directory_is_data_only(path: Path) -> bool:
    """Return whether all meaningful files under path are data artifacts."""
    found_data = False
    for current, directories, files in os.walk(path):
        directories[:] = [
            name
            for name in directories
            if name.casefold() not in EXCLUDED_NAMES
            and not name.casefold().startswith(".venv")
            and not name.casefold().endswith(EXCLUDED_SUFFIXES)
        ]
        for name in files:
            suffix = Path(current, name).suffix.casefold()
            if suffix not in DATA_ONLY_SUFFIXES:
                return False
            found_data = True
    return found_data


def _direct_source_count(path: Path) -> int:
    try:
        return sum(
            item.is_file() and item.suffix.casefold() in SOURCE_SUFFIXES
            for item in path.iterdir()
        )
    except OSError:
        return 0


def is_meaningful_boundary(path: Path, root: Path) -> bool:
    """Identify deployable services, apps, and substantial subsystem folders."""
    if not path.is_dir() or is_excluded(path, root) or directory_is_data_only(path):
        return False

    relative = path.resolve().relative_to(root.resolve())
    if not relative.parts:
        return True

    name = path.name.casefold()
    if len(relative.parts) == 1:
        if name in KNOWN_BOUNDARIES or (path / README_NAME).is_file():
            return True
        if any((path / marker).is_file() for marker in BOUNDARY_FILES):
            return True
        return _direct_source_count(path) >= 2

    if relative.parts[0].casefold() in SUPPORT_BOUNDARIES:
        return False
    if len(relative.parts) == 2:
        return (
            name not in NESTED_NON_BOUNDARIES
            and (path / "__init__.py").is_file()
            and _direct_source_count(path) >= 4
        )
    return False


def discover_boundaries(root: Path) -> tuple[Path, ...]:
    """Discover README boundaries deterministically without following symlinks."""
    boundaries = [root]
    try:
        top_level = sorted(
            (
                item
                for item in root.iterdir()
                if item.is_dir() and not item.is_symlink()
            ),
            key=lambda item: item.name.casefold(),
        )
    except OSError:
        return tuple(boundaries)

    for directory in top_level:
        if not is_meaningful_boundary(directory, root):
            continue
        boundaries.append(directory)
        try:
            children = sorted(
                (
                    item
                    for item in directory.iterdir()
                    if item.is_dir() and not item.is_symlink()
                ),
                key=lambda item: item.name.casefold(),
            )
        except OSError:
            continue
        boundaries.extend(
            child for child in children if is_meaningful_boundary(child, root)
        )
    return tuple(boundaries)


def discover_readmes(root: Path) -> tuple[Path, ...]:
    """Find policy-relevant READMEs while pruning excluded trees."""
    readmes: list[Path] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        if is_excluded(directory, root):
            continue
        readme = directory / README_NAME
        if readme.is_file():
            readmes.append(readme)
        try:
            pending.extend(
                item
                for item in directory.iterdir()
                if item.is_dir() and not item.is_symlink()
            )
        except OSError:
            continue
    return tuple(sorted(readmes, key=lambda item: item.as_posix().casefold()))


def _normalize_heading(value: str) -> str:
    without_markup = re.sub(r"[`*_]", "", value)
    return re.sub(r"[^a-z0-9]+", " ", without_markup.casefold()).strip()


def _document_topics(body: str) -> set[str]:
    values = HEADING_RE.findall(body)
    values.extend(LABEL_RE.findall(FENCE_RE.sub("", body)))
    return {_normalize_heading(value) for value in values}


def _missing_sections(body: str) -> list[str]:
    topics = _document_topics(body)
    return [
        canonical
        for canonical, aliases in REQUIRED_SECTIONS
        if not any(alias in topics for alias in aliases)
    ]


def _normalized_body(body: str) -> str:
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    body = HEADING_RE.sub("", body, count=1)
    body = re.sub(r"\s+", " ", body).strip().casefold()
    return body


def _link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    return target.split(maxsplit=1)[0]


def _relative_link_findings(readme: Path, root: Path, body: str) -> list[Finding]:
    findings: list[Finding] = []
    link_body = FENCE_RE.sub("", body)
    raw_targets = INLINE_LINK_RE.findall(link_body)
    raw_targets.extend(REFERENCE_LINK_RE.findall(link_body))

    for raw_target in raw_targets:
        target = unquote(_link_target(raw_target))
        if (
            not target
            or target.startswith(("#", "/", "\\"))
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
        ):
            continue
        path_part = target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]
        if not path_part:
            continue
        candidate = (readme.parent / path_part).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            message = f"relative link escapes repository: {target}"
        else:
            if candidate.exists():
                continue
            message = f"relative link target does not exist: {target}"
        findings.append(Finding(Severity.ERROR, "broken-link", readme, message))
    return findings


def _module_aliases(name: str) -> tuple[str, ...]:
    words = name.casefold().replace("-", "_").split("_")
    aliases = {name.casefold(), " ".join(words)}
    if words and words[-1] in {"app", "service", "ui"}:
        aliases.add(" ".join(words[:-1]))
    return tuple(alias for alias in aliases if alias)


def validate(root: Path) -> tuple[Finding, ...]:
    """Run all checks and return stable, sorted findings."""
    root = root.resolve()
    findings: list[Finding] = []
    boundaries = discover_boundaries(root)
    readmes = discover_readmes(root)
    bodies: dict[Path, str] = {}

    for boundary in boundaries:
        readme = boundary / README_NAME
        if not readme.is_file():
            findings.append(
                Finding(
                    Severity.ERROR,
                    "missing-readme",
                    boundary,
                    "meaningful boundary has no README.md",
                )
            )

    for readme in readmes:
        try:
            body = readme.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "unreadable",
                    readme,
                    f"cannot read UTF-8 README: {error}",
                )
            )
            continue
        bodies[readme] = body
        strict = CONTRACT_MARKER in body
        severity = Severity.ERROR if strict else Severity.WARNING

        missing = _missing_sections(body)
        if missing:
            findings.append(
                Finding(
                    severity,
                    "missing-sections",
                    readme,
                    "missing topics: " + ", ".join(missing),
                )
            )
        for pattern in PLACEHOLDER_PATTERNS:
            match = pattern.search(FENCE_RE.sub("", body))
            if match is not None:
                findings.append(
                    Finding(
                        severity,
                        "placeholder",
                        readme,
                        f"placeholder text found: {match.group(0)!r}",
                    )
                )
        findings.extend(_relative_link_findings(readme, root, body))

    duplicate_groups: dict[str, list[Path]] = {}
    for readme, body in bodies.items():
        normalized = _normalized_body(body)
        if normalized:
            duplicate_groups.setdefault(normalized, []).append(readme)
    for group in duplicate_groups.values():
        if len(group) < 2:
            continue
        relative_paths = ", ".join(
            path.relative_to(root).as_posix() or README_NAME for path in group
        )
        for readme in group:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "duplicate-body",
                    readme,
                    f"README body duplicates: {relative_paths}",
                )
            )

    root_docs = []
    for document in sorted(root.glob("*.md")):
        try:
            root_docs.append(document.read_text(encoding="utf-8").casefold())
        except OSError, UnicodeError:
            continue
    root_text = "\n".join(root_docs)
    for boundary in boundaries:
        relative = boundary.relative_to(root)
        if len(relative.parts) != 1 or boundary.name.casefold() in SUPPORT_BOUNDARIES:
            continue
        if not any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", root_text)
            for alias in _module_aliases(boundary.name)
        ):
            findings.append(
                Finding(
                    Severity.ERROR,
                    "unreferenced-module",
                    boundary,
                    "major module is not referenced from a root Markdown document",
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.severity != Severity.ERROR,
                item.path.as_posix().casefold(),
                item.code,
                item.message,
            ),
        )
    )


def _display_path(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return path.as_posix()
    return relative.as_posix() or "."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only validation for Moksha AI README boundaries.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="fail on legacy README topic and placeholder warnings",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"error: repository root is not a directory: {root}", file=sys.stderr)
        return 2

    findings = validate(root)
    for finding in findings:
        print(
            f"{finding.severity}: {finding.code}: "
            f"{_display_path(finding.path, root)}: {finding.message}"
        )

    errors = sum(finding.severity == Severity.ERROR for finding in findings)
    warnings = sum(finding.severity == Severity.WARNING for finding in findings)
    print(f"README validation: {errors} error(s), {warnings} warning(s)")
    if errors or (args.warnings_as_errors and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
