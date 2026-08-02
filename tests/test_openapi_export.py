"""Regression tests for the generated browser API contract."""

from collections import Counter

from scripts.export_openapi import build_schema, operation_id


def test_operation_ids_are_stable_and_readable():
    assert operation_id("POST", "/api/v1/chats/{id}/runs/") == "postApiV1ChatsByIdRuns"


def test_export_contains_only_canonical_v1_paths_and_unique_operations():
    schema = build_schema()
    paths = schema["paths"]
    assert paths
    assert all(path.startswith("/api/v1/") for path in paths)
    assert "/api/v1/runs/{id}/events/" in paths
    assert not any("/chats/runs/" in path for path in paths)

    operation_ids = [
        operation["operationId"]
        for path_item in paths.values()
        for method, operation in path_item.items()
        if method in {"delete", "get", "patch", "post", "put"}
    ]
    duplicates = [value for value, count in Counter(operation_ids).items() if count > 1]
    assert not duplicates
