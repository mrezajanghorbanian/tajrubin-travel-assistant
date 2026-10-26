"""Harness²-inspired deterministic probe gate, not upstream Harness² runtime.

Uses synthetic bilingual scenarios to pin traveler-preview behavior. Optional
optimization experiments must improve this baseline without safety regression.
No external API, network execution, paid models or private data.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.assistant.trip_preview import preview_trip_request


DEFAULT_CASES = Path(__file__).resolve().parent / "fixtures" / "harness2_travel_preview_v1.json"


def evaluate_travel_preview(path: Path = DEFAULT_CASES) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("dataset_version") != "1.0":
        raise ValueError("Unknown evaluation dataset version")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) > 1000:
        raise ValueError("Cases must be a non-empty bounded list")
    actual = []
    seen = set()
    for entry in cases:
        case_id, request, expected = entry["id"], entry["request"], entry["expected_status"]
        if case_id in seen:
            raise ValueError("Duplicate evaluation case id")
        seen.add(case_id)
        result = preview_trip_request(request)
        actual.append({
            "id": case_id,
            "expected": expected,
            "actual": result.status,
            "pass": result.status == expected,
            "no_fabricated_schedule": result.schedule is None,
            "no_false_live_verification": result.live_verified is False,
        })
    total = len(actual)
    passed = sum(x["pass"] and x["no_fabricated_schedule"] and x["no_false_live_verification"] for x in actual)
    return {
        "dataset_version": data["dataset_version"],
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4),
        "cases": actual,
    }


def main() -> int:
    report = evaluate_travel_preview()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
