"""An ISO range cannot erase explicit invalid or conflicting day counts."""
import json
import subprocess
import sys

import pytest

from app.assistant.planning_readiness import analyze_planning_request
from app.assistant.traveler_intent import analyze_traveler_intent
from app.assistant.traveler_intent_v2 import analyze_traveler_intent_v2


AMBIGUOUS = [
    "Plan a 3 day or 5 day trip to Tehran",
    "برای تهران برنامه سفر ۳ روز یا ۵ روز میخواهم",
    "Plan a 90 day trip to Tehran",
    "برای تهران برنامه سفر ۹۰ روز میخواهم",
    "Plan a 0 day trip to Tehran",
    "برای تهران برنامه سفر ۰ روز میخواهم",
    "Plan a 3 day or 90 day trip to Tehran",
    "برای تهران برنامه سفر ۳ روز یا ۹۰ روز میخواهم",
    "Plan a 3 day or 0 day trip to Tehran",
    "برای تهران برنامه سفر ۳ روز یا ۰ روز میخواهم",
]
RANGE = " from 2026-11-03 to 2026-11-05"


@pytest.mark.parametrize("prompt", AMBIGUOUS)
@pytest.mark.parametrize("with_dates", [False, True])
def test_explicit_unresolved_duration_blocks_draft_even_with_dates(prompt, with_dates):
    text = prompt + (RANGE if with_dates else "")
    base = analyze_traveler_intent(text)
    assert base.duration_days is None
    intent = analyze_traveler_intent_v2(text)
    assert "duration_days" in intent.unresolved_fields
    result = analyze_planning_request(text)
    assert result.status == "needs_clarification"
    assert result.blockers == ("duration_days",)
    assert result.clarification_question
    assert result.draft_specification is None
    if with_dates:
        assert result.intent.travel_dates is not None


@pytest.mark.parametrize("prompt", [
    "Plan a 3 day trip to Tehran",
    "برای تهران برنامه سفر ۳ روز میخواهم",
    "Plan a 3 day trip to Tehran, 3 days total",
    "برای تهران برنامه سفر سه روز میخواهم؛ ۳ روز",
    "Plan a 3 day trip to Tehran in 5 days",
    "برای تهران برنامه سفر ۳ روز میخواهم؛ ۵ روز بعد حرکت میکنم",
])
def test_consistent_counts_and_departure_mentions_remain_usable(prompt):
    result = analyze_planning_request(prompt + RANGE)
    assert result.status == "ready_for_draft"
    assert result.blockers == ()
    assert result.draft_specification.duration_days == 3
    assert result.draft_specification.duration_source == "explicit"
    assert result.draft_specification.logistics_verified is False


@pytest.mark.parametrize("prompt", [
    "Plan a trip to Tehran",
    "Plan a trip to Tehran in 5 days",
    "Plan a trip to Tehran in-5-days",
])
def test_date_only_request_can_still_derive_duration(prompt):
    result = analyze_planning_request(prompt + RANGE)
    assert result.status == "ready_for_draft"
    assert result.draft_specification.duration_days == 3
    assert result.draft_specification.duration_source == "inclusive_iso_date_range"


@pytest.mark.parametrize("prompt", [AMBIGUOUS[0], AMBIGUOUS[3], AMBIGUOUS[6]])
def test_unified_cli_does_not_publish_unresolved_draft_inputs(prompt):
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "app.assistant", prompt + RANGE, "--format", "json"],
        capture_output=True, encoding="utf-8", check=True,
    )
    result = json.loads(completed.stdout)
    assert result["kind"] == "planning_readiness"
    assert result["planning"]["status"] == "needs_clarification"
    assert result["planning"]["draft_specification"] is None
    assert result["knowledge"] is None
    assert result["live_verified"] is False


@pytest.mark.parametrize("prompt", [AMBIGUOUS[0], AMBIGUOUS[3], AMBIGUOUS[6]])
def test_trip_preview_stops_before_activity_or_release_requirements(prompt):
    from app.assistant.trip_preview import preview_trip_request

    result = preview_trip_request(prompt + RANGE)
    assert result.status == "needs_clarification"
    assert result.readiness.blockers == ("duration_days",)
    assert result.schedule is None
    assert result.source_document_ids == ()
    assert result.live_verified is False
