"""Two explicit day-count alternatives must not collapse to the last number."""
import json
import subprocess
import sys

import pytest

from app.assistant.planning_readiness import analyze_planning_request
from app.assistant.traveler_intent import analyze_traveler_intent


RANGE = " from 2026-11-03 to 2026-11-07"
AMBIGUOUS = [
    "Plan a 3 or 5 days trip to Tehran",
    "Plan a 3 to 5 day trip to Tehran",
    "Plan a three or five days trip to Tehran",
    "برای تهران برنامه سفر ۳ یا ۵ روز میخواهم",
    "برای تهران برنامه سفر ۳ تا ۵ روز میخواهم",
    "برای تهران برنامه سفر سه یا پنج روز میخواهم",
    "Plan a 0 or 5 days trip to Tehran",
    "برای تهران برنامه سفر ۰ تا ۵ روز میخواهم",
    "Plan a 90 to 5 days trip to Tehran",
    "برای تهران برنامه سفر ۹۰ یا ۵ روز میخواهم",
]


@pytest.mark.parametrize("prompt", AMBIGUOUS)
@pytest.mark.parametrize("with_dates", [False, True])
def test_shared_unit_alternatives_need_clarification(prompt, with_dates):
    text = prompt + (RANGE if with_dates else "")
    assert analyze_traveler_intent(text).duration_days is None
    result = analyze_planning_request(text)
    assert result.status == "needs_clarification"
    assert result.blockers == ("duration_days",)
    assert result.draft_specification is None


@pytest.mark.parametrize("prompt", [
    "Plan a 5 or 5 days trip to Tehran",
    "Plan a five to 5 days trip to Tehran",
    "برای تهران برنامه سفر پنج یا ۵ روز میخواهم",
    "برای تهران برنامه سفر ۵ تا ۵ روز میخواهم",
])
def test_identical_values_still_resolve_to_one_duration(prompt):
    result = analyze_planning_request(prompt + RANGE)
    assert result.status == "ready_for_draft"
    assert result.draft_specification.duration_days == 5
    assert result.draft_specification.duration_source == "explicit"
    assert result.draft_specification.logistics_verified is False


@pytest.mark.parametrize("prompt", [
    "Plan a trip to Tehran in 3 or 5 days",
    "Plan a trip to Tehran 3 to 5 days later",
    "برای تهران برنامه سفر میخواهم؛ ۳ یا ۵ روز بعد حرکت میکنم",
    "برای تهران برنامه سفر میخواهم؛ سه تا پنج روز دیگه حرکت میکنم",
])
def test_shared_unit_departure_is_not_trip_duration(prompt):
    assert analyze_traveler_intent(prompt).duration_days is None
    result = analyze_planning_request(prompt + RANGE)
    assert result.status == "ready_for_draft"
    assert result.draft_specification.duration_days == 5
    assert result.draft_specification.duration_source == "inclusive_iso_date_range"


@pytest.mark.parametrize("prompt", [AMBIGUOUS[0], AMBIGUOUS[3]])
def test_unified_cli_does_not_publish_last_alternative_as_duration(prompt):
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "app.assistant", prompt + RANGE, "--format", "json"],
        capture_output=True, encoding="utf-8", check=True,
    )
    result = json.loads(completed.stdout)
    assert result["kind"] == "planning_readiness"
    assert result["planning"]["status"] == "needs_clarification"
    assert result["planning"]["draft_specification"] is None
    assert result["live_verified"] is False


@pytest.mark.parametrize("prompt", [
    "Does the Tehran museum offer a 3 to 5 day pass?",
    "بلیت ۳ یا ۵ روز موزه تهران چیست؟",
])
def test_day_range_in_factual_question_does_not_imply_planning(prompt):
    result = analyze_planning_request(prompt)
    assert result.status == "not_planning"
    assert result.draft_specification is None
