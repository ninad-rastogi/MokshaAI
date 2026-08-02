"""Tests for corpus-neutral Ollama benchmark discovery."""

from scripts.benchmark_ollama import (
    build_cases,
    discover_collection_names,
    qualification_summary,
)


def test_benchmark_discovers_every_pdf_collection(tmp_path):
    (tmp_path / "Collection One").mkdir()
    (tmp_path / "Collection One" / "volume.pdf").touch()
    (tmp_path / "Collection Two" / "nested").mkdir(parents=True)
    (tmp_path / "Collection Two" / "nested" / "book.pdf").touch()
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "readme.txt").touch()

    assert discover_collection_names(tmp_path) == [
        "Collection One",
        "Collection Two",
    ]


def test_benchmark_cases_use_discovered_collection_without_fixed_text():
    cases = build_cases(["New Collection"])
    rendered = repr(cases)

    assert "New Collection" in rendered
    assert "benchmark_excerpt.txt" in rendered
    assert "Mahabharata" not in rendered
    assert "Krishna" not in rendered
    assert {case.name for case in cases} == {
        "structured_routing_json",
        "safety_routing_json",
        "grounded_citation",
        "typed_citation_json",
        "honest_no_evidence",
        "hindi_guidance",
        "sanskrit_context_grounding",
    }


def test_qualification_summary_reports_measured_throughput_gap():
    report = {
        "pass_rate": 1.0,
        "minimum_tokens_per_second": 17.4,
        "median_tokens_per_second": 21.17,
    }

    summary = qualification_summary(report, min_tokens_per_second=20)

    assert summary == {
        "functional_passed": True,
        "throughput_passed": False,
        "qualified": False,
        "target_min_tokens_per_second": 20,
        "measured_safe_minimum_tokens_per_second": 17.4,
        "measured_median_tokens_per_second": 21.17,
    }
