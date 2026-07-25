"""Benchmark Ollama models against Moksha AI's critical response contracts."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass(frozen=True)
class Case:
    name: str
    messages: list[dict[str, str]]
    expected_category: str | None = None
    required_text: str | None = None
    require_devanagari: bool = False


CASES = [
    Case(
        name="classifier_scripture",
        expected_category="SCRIPTURE",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the query as SCRIPTURE, GUIDANCE, or CASUAL. "
                    'Return only JSON: {"category":"...","reasoning":"..."}'
                ),
            },
            {
                "role": "user",
                "content": "What does the Bhagavad Gita say about karma?",
            },
        ],
    ),
    Case(
        name="classifier_guidance",
        expected_category="GUIDANCE",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the query as SCRIPTURE, GUIDANCE, or CASUAL. "
                    'Return only JSON: {"category":"...","reasoning":"..."}'
                ),
            },
            {"role": "user", "content": "How can I remain calm when I am worried?"},
        ],
    ),
    Case(
        name="grounded_citation",
        required_text="[Bhagavad Gita, sample.pdf, p. 2]",
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer only from the supplied context. Cite every factual "
                    "claim with the citation exactly as supplied."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Context: Krishna teaches that one has a right to action, "
                    "not to its fruits. [Bhagavad Gita, sample.pdf, p. 2]\n"
                    "Question: What attitude should one have toward action?"
                ),
            },
        ],
    ),
    Case(
        name="hindi_guidance",
        require_devanagari=True,
        messages=[
            {
                "role": "system",
                "content": "उत्तर संक्षिप्त, स्पष्ट और केवल हिंदी में दें।",
            },
            {"role": "user", "content": "मन को शांत रखने के दो व्यावहारिक उपाय बताइए।"},
        ],
    ),
]


def parse_json_response(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        value = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def run_case(
    base_url: str,
    model: str,
    case: Case,
    timeout: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    response = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": case.messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "num_ctx": 8192,
                "num_predict": 256,
                "temperature": 0.1,
                "seed": 42,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    elapsed = time.perf_counter() - started
    payload = response.json()
    content = payload.get("message", {}).get("content", "")
    eval_count = int(payload.get("eval_count") or 0)
    eval_duration = int(payload.get("eval_duration") or 0)
    tokens_per_second = (
        eval_count / (eval_duration / 1_000_000_000) if eval_duration else 0.0
    )

    passed = bool(content.strip())
    details: dict[str, Any] = {}
    if case.expected_category:
        parsed = parse_json_response(content)
        actual = parsed.get("category") if parsed else None
        passed = actual == case.expected_category
        details["expected_category"] = case.expected_category
        details["actual_category"] = actual
        details["valid_json"] = parsed is not None
    if case.required_text:
        citation_present = case.required_text in content
        passed = passed and citation_present
        details["required_citation_present"] = citation_present
    if case.require_devanagari:
        devanagari_present = any("\u0900" <= char <= "\u097f" for char in content)
        passed = passed and devanagari_present
        details["devanagari_present"] = devanagari_present

    return {
        "case": case.name,
        "passed": passed,
        "elapsed_seconds": round(elapsed, 3),
        "tokens_per_second": round(tokens_per_second, 2),
        "prompt_tokens": payload.get("prompt_eval_count"),
        "generated_tokens": eval_count,
        "response": content,
        **details,
    }


def benchmark_model(
    base_url: str,
    model: str,
    runs: int,
    timeout: float,
) -> dict[str, Any]:
    results = [
        run_case(base_url, model, case, timeout) for _ in range(runs) for case in CASES
    ]
    speeds = [
        result["tokens_per_second"] for result in results if result["tokens_per_second"]
    ]
    return {
        "model": model,
        "runs_per_case": runs,
        "passed": sum(bool(result["passed"]) for result in results),
        "total": len(results),
        "pass_rate": round(
            sum(bool(result["passed"]) for result in results) / len(results),
            3,
        ),
        "median_tokens_per_second": (
            round(statistics.median(speeds), 2) if speeds else 0.0
        ),
        "minimum_tokens_per_second": round(min(speeds), 2) if speeds else 0.0,
        "results": results,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "moksha-qwen3:4b-instruct-q3km",
            "llama3.2:3b",
            "qwen3.5:9b",
        ],
    )
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    model_reports: list[dict[str, Any]] = [
        benchmark_model(args.base_url, model, args.runs, args.timeout)
        for model in args.models
    ]
    report: dict[str, Any] = {
        "generated_at_unix": int(time.time()),
        "context_length": 8192,
        "models": model_reports,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")

    selected = next(
        (
            model
            for model in model_reports
            if model["model"] == "moksha-qwen3:4b-instruct-q3km"
        ),
        None,
    )
    if not selected:
        return 0
    return (
        0
        if selected["pass_rate"] == 1.0 and selected["minimum_tokens_per_second"] >= 20
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
