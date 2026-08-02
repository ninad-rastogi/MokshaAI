"""Export the canonical v1 API schema with stable, unique operation IDs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, cast

import django

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings")
django.setup()

HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}


def operation_id(method: str, path: str) -> str:
    """Build a readable operation ID from one method/path pair."""
    parts = [method.lower()]
    for component in path.strip("/").split("/"):
        parameter = re.fullmatch(r"\{([^}]+)\}", component)
        if parameter:
            parts.extend(("by", parameter.group(1)))
        else:
            parts.extend(re.findall(r"[A-Za-z0-9]+", component))
    words = [word.lower() for word in parts if word]
    return words[0] + "".join(word.capitalize() for word in words[1:])


def build_schema() -> dict[str, Any]:
    """Generate and normalize only the public v1 API contract."""
    from django.urls import URLPattern, URLResolver
    from rest_framework.schemas.openapi import SchemaGenerator

    from moksha.urls import urlpatterns

    root_patterns = cast(list[URLPattern | URLResolver], urlpatterns)
    v1_patterns = [
        pattern
        for pattern in root_patterns
        if str(pattern.pattern).startswith("api/v1/")
    ]
    with warnings.catch_warnings():
        # DRF checks its temporary IDs before this exporter replaces them.
        warnings.filterwarnings(
            "ignore",
            message="You have a duplicated operationId in your OpenAPI schema.*",
            category=UserWarning,
        )
        schema = SchemaGenerator(
            title="Moksha AI API",
            description="Canonical Django REST API used by Moksha clients.",
            version="1.0.0",
            patterns=v1_patterns,
        ).get_schema(public=True)
    if not isinstance(schema, dict):
        raise TypeError("DRF did not return an OpenAPI document")
    schema_document = cast(dict[str, Any], schema)

    all_paths = schema_document.get("paths", {})
    canonical_paths: dict[str, Any] = {}
    operation_ids: list[str] = []
    for path in sorted(all_paths):
        if not path.startswith("/api/v1/"):
            continue
        item = all_paths[path]
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            stable_id = operation_id(method, path)
            operation["operationId"] = stable_id
            operation_ids.append(stable_id)
        canonical_paths[path] = item

    duplicates = sorted(
        value for value, count in Counter(operation_ids).items() if count > 1
    )
    if duplicates:
        raise RuntimeError(f"Duplicate operation IDs: {', '.join(duplicates)}")
    if not canonical_paths:
        raise RuntimeError("No /api/v1/ paths were generated")

    schema_document["paths"] = canonical_paths
    schema_document["info"] = {
        **schema_document.get("info", {}),
        "title": "Moksha AI API",
        "version": "1.0.0",
    }
    return schema_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rendered = json.dumps(build_schema(), indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
