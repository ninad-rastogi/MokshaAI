"""Host-only Moksha setup commands."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HARDWARE_SCHEMA_VERSION = 1


def _whichllm_cache_dir() -> Path:
    configured = os.getenv("MOKSHA_WHICHLLM_CACHE_DIR")
    if configured:
        path = Path(configured).expanduser().resolve()
    else:
        path = Path.home() / ".cache" / "moksha-ai"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _recommendations(top: int, context_length: int, cache_dir: Path) -> list[dict]:
    environment = os.environ.copy()
    environment["XDG_CACHE_HOME"] = str(cache_dir)
    command = [
        sys.executable,
        "-m",
        "whichllm",
        "--json",
        "--top",
        str(top),
        "--context-length",
        str(context_length),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=300,
    )
    payload: Any = json.loads(completed.stdout)
    if isinstance(payload, dict):
        candidates = payload.get("models", payload.get("recommendations", []))
    else:
        candidates = payload
    if not isinstance(candidates, list):
        raise TypeError("whichllm_output_invalid")
    return [item for item in candidates[:top] if isinstance(item, dict)]


def scan_model_hardware(top: int, context_length: int) -> int:
    if sys.platform != "win32":
        print(
            "error: model hardware scan is supported only on the Windows host",
            file=sys.stderr,
        )
        return 2

    # Deliberately local: Django imports and containers never load WhichLLM.
    from whichllm.hardware.detector import detect_hardware

    hardware = detect_hardware()
    payload = dataclasses.asdict(hardware)
    whichllm_version = importlib.metadata.version("whichllm")
    cache_dir = _whichllm_cache_dir()
    try:
        recommendations = _recommendations(top, context_length, cache_dir)
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        RuntimeError,
        TypeError,
    ):
        print(
            "error: WhichLLM could not produce ranked recommendations",
            file=sys.stderr,
        )
        return 1

    driver_parts: list[str] = []
    for gpu in payload.get("gpus", []):
        if isinstance(gpu, dict):
            driver_parts.extend(
                str(gpu.get(key, ""))
                for key in ("name", "cuda_version", "rocm_version")
            )
    driver_fingerprint = hashlib.sha256(
        "|".join(driver_parts).encode("utf-8")
    ).hexdigest()
    profile_material = {
        "schema_version": HARDWARE_SCHEMA_VERSION,
        "whichllm_version": whichllm_version,
        "driver_fingerprint": driver_fingerprint,
        "hardware": payload,
        "recommendations": recommendations,
        "context_length": context_length,
    }
    profile_hash = hashlib.sha256(
        json.dumps(
            profile_material,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings")
    import django

    django.setup()
    from django.db import OperationalError, ProgrammingError, transaction

    from llm.models import HardwareProfile

    catalog_version = os.getenv("MOKSHA_MODEL_CATALOG_VERSION", "")
    try:
        with transaction.atomic():
            HardwareProfile.objects.exclude(profile_hash=profile_hash).update(
                stale=True
            )
            profile, _ = HardwareProfile.objects.update_or_create(
                profile_hash=profile_hash,
                defaults={
                    "schema_version": HARDWARE_SCHEMA_VERSION,
                    "whichllm_version": whichllm_version,
                    "catalog_version": catalog_version,
                    "driver_fingerprint": driver_fingerprint,
                    "payload": payload,
                    "recommendations": recommendations,
                    "stale": False,
                },
            )
    except OperationalError, ProgrammingError:
        print(
            "error: database is not ready; run migrations before scanning hardware",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "profile_hash": profile.profile_hash,
                "whichllm_version": whichllm_version,
                "recommendation_count": len(recommendations),
                "stale": profile.stale,
            },
            separators=(",", ":"),
        )
    )
    return 0


def rewrap_byok(target_version: int) -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings")
    import django

    django.setup()
    from llm.security import (
        DecryptionFailed,
        KeyUnavailable,
        rewrap_byok_connections,
    )

    try:
        updated = rewrap_byok_connections(target_version)
    except DecryptionFailed, KeyUnavailable:
        print("error: BYOK rewrap failed; database was not changed", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "rewrapped_connections": updated,
                "key_version": target_version,
            },
            separators=(",", ":"),
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="moksha")
    root = parser.add_subparsers(dest="command", required=True)
    setup = root.add_parser("setup", help="run explicit host setup actions")
    setup_commands = setup.add_subparsers(dest="setup_command", required=True)
    model = setup_commands.add_parser("model", help="manage the host model platform")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    scan = model_commands.add_parser("scan", help="scan hardware with WhichLLM")
    scan.add_argument("--top", type=int, default=10, choices=range(1, 51))
    scan.add_argument("--context-length", type=int, default=8192)
    security = root.add_parser("security", help="run explicit secret operations")
    security_commands = security.add_subparsers(
        dest="security_command",
        required=True,
    )
    rewrap = security_commands.add_parser(
        "rewrap-byok",
        help="atomically re-encrypt stored BYOK keys",
    )
    rewrap.add_argument("--target-version", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "setup" and args.model_command == "scan":
        if args.context_length < 1024 or args.context_length > 1_048_576:
            print(
                "error: context length is outside the supported range", file=sys.stderr
            )
            return 2
        return scan_model_hardware(args.top, args.context_length)
    if args.command == "security" and args.security_command == "rewrap-byok":
        if args.target_version <= 0:
            print("error: target key version must be positive", file=sys.stderr)
            return 2
        return rewrap_byok(args.target_version)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
