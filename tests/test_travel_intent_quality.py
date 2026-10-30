"""Independent field-level travel intent quality checks.

This dataset is a fixed regression set, not blind validation or Harness² itself.
"""
import json
from pathlib import Path

from app.assistant.trip_preview import preview_trip_request

CASES=Path(__file__).parent/"fixtures"/"travel_intent_quality_v1.json"


def test_independent_intent_quality_cases():
    data=json.loads(CASES.read_text(encoding="utf-8"))
    assert data["dataset_version"]=="1.0"
    failures=[]
    for case in data["cases"]:
        result=preview_trip_request(case["request"])
        expected=case["expected"]
        base=result.readiness.intent
        observed={
            "status":result.status,
            "destination":base.base.destination,
            "duration_days":base.base.duration_days,
            "origin":base.origin,
            "budget":(
                {"amount":str(base.budget.amount),"unit":base.budget.unit}
                if base.budget else None
            ),
        }
        if observed!=expected:
            failures.append({"case":case["id"],"expected":expected,"observed":observed})
        assert result.live_verified is False
        assert result.schedule is None
    assert len(data["cases"])==28
    assert not failures, failures
