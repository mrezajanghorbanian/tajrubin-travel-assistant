"""Fixed bilingual offline probe, adapted from Harness² evaluation methodology."""
from tests.harness2_probe import evaluate_travel_preview

def test_32_bilingual_traveler_cases_never_regress():
    report=evaluate_travel_preview()
    mismatches=[
        (case["id"],case["expected"],case["actual"])
        for case in report["cases"] if not case["pass"]
    ]
    assert report["total"] == 32
    assert report["failed"] == 0, f"Preview status regressions: {mismatches}"

def test_no_synthetic_case_claims_live_verified():
    report=evaluate_travel_preview()
    assert all(c["no_false_live_verification"] for c in report["cases"])
    assert all(c["no_fabricated_schedule"] for c in report["cases"])
