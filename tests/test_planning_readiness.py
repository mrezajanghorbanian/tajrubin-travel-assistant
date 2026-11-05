"""Behavioral acceptance tests for the non-bookable travel planning gate."""

from datetime import date
from decimal import Decimal
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.assistant.planning_readiness import (
    TripDraftSpecificationV1,
    analyze_planning_request,
)


def test_single_city_with_duration_is_ready_only_for_draft():
    result = analyze_planning_request("Plan a 3 day trip to Shiraz")
    assert result.status == "ready_for_draft"
    assert result.blockers == ()
    assert result.draft_specification.destinations == ("Shiraz",)
    assert result.draft_specification.logistics_verified is False


def test_persian_trip_preserves_interests_without_invented_budget():
    result = analyze_planning_request(
        "۳ روز شیراز، معماری و غذاهای محلی دوست دارم"
    )
    assert result.status == "ready_for_draft"
    assert result.draft_specification.interests == ("food", "art_culture")
    assert result.draft_specification.budget is None
    assert result.draft_specification.dates is None


def test_two_cities_with_no_explicit_order_require_clarification():
    result = analyze_planning_request("Plan a 5 day trip to Tehran and Shiraz")
    assert result.status == "needs_clarification"
    assert result.blockers == ("route_order",)
    assert result.draft_specification is None
    assert result.clarification_question


def test_explicit_sequence_is_allowed_as_draft_not_validated_route():
    result = analyze_planning_request("Plan a 5 day trip to Shiraz then Yazd")
    assert result.status == "ready_for_draft"
    assert result.draft_specification.destinations == ("Shiraz", "Yazd")
    assert result.draft_specification.route_order_explicit is True
    assert result.draft_specification.logistics_verified is False


def test_from_origin_is_not_an_itinerary_stop():
    result = analyze_planning_request("Plan a 3 day trip from Tehran to Shiraz")
    assert result.status == "ready_for_draft"
    assert result.draft_specification.origin == "Tehran"
    assert result.draft_specification.destinations == ("Shiraz",)


def test_dates_derive_inclusive_day_count_only_from_two_dates():
    result = analyze_planning_request(
        "Plan a trip to Yazd from 2026-11-03 to 2026-11-06"
    )
    spec = result.draft_specification
    assert result.status == "ready_for_draft"
    assert spec.duration_days == 4
    assert spec.duration_source == "inclusive_iso_date_range"
    assert spec.dates.start_date == date(2026, 11, 3)


def test_explicit_days_and_dates_that_agree_are_valid_draft():
    result = analyze_planning_request(
        "Plan a 4 day trip to Yazd from 2026-11-03 to 2026-11-06"
    )
    assert result.status == "ready_for_draft"
    assert result.draft_specification.duration_source == "explicit"


def test_explicit_days_and_dates_that_conflict_block_draft():
    result = analyze_planning_request(
        "Plan a 3 day trip to Yazd from 2026-11-03 to 2026-11-06"
    )
    assert result.status == "needs_clarification"
    assert "duration_conflict" in result.blockers
    assert result.draft_specification is None


def test_jalali_date_requires_calendar_clarification():
    result = analyze_planning_request(
        "۳ روز شیراز، تاریخ ۱۴۰۵/۰۸/۱۵"
    )
    assert result.status == "needs_clarification"
    assert "travel_dates" in result.blockers


def test_unknown_city_requires_clarification():
    result = analyze_planning_request("Plan a 3 day trip to Atlantis")
    assert result.status == "needs_clarification"
    assert result.blockers == ("destinations",)


def test_unknown_duration_requires_clarification():
    result = analyze_planning_request("Plan a trip to Tehran")
    assert result.status == "needs_clarification"
    assert result.blockers == ("duration_days",)


def test_invalid_iso_date_cannot_pass_through():
    result = analyze_planning_request(
        "Plan a 3 day trip to Tehran on 2026-02-31"
    )
    assert result.status == "needs_clarification"
    assert "travel_dates" in result.blockers


def test_unparseable_budget_does_not_vanish():
    result = analyze_planning_request("Plan a 3 day trip to Tehran. Budget 500")
    assert result.status == "needs_clarification"
    assert "budget" in result.blockers


def test_explicit_budget_preserves_unit_and_amount():
    result = analyze_planning_request(
        "۴ روز شیراز، بودجه ۵ میلیون تومان"
    )
    assert result.status == "ready_for_draft"
    assert result.draft_specification.budget.amount == Decimal("5000000")
    assert result.draft_specification.budget.unit == "TOMAN"


def test_conflicting_budgets_block_draft():
    result = analyze_planning_request(
        "Plan a 3 day trip to Tehran. Budget 300 USD or 500 EUR"
    )
    assert result.status == "needs_clarification"
    assert result.blockers == ("budget",)


def test_question_is_not_force_converted_to_itinerary():
    result = analyze_planning_request("Tell me about Tehran museums")
    assert result.status == "not_planning"
    assert result.draft_specification is None
    assert result.clarification_question is None


def test_zero_booking_claims_and_no_live_verified_field():
    result = analyze_planning_request("Plan a 3 day trip to Tehran")
    payload = result.model_dump()
    assert payload["draft_specification"]["logistics_verified"] is False
    assert "booking" not in payload["draft_specification"]


def test_strict_spec_rejects_fake_verified_logistics():
    result = analyze_planning_request("Plan a 3 day trip to Tehran")
    data = result.draft_specification.model_dump()
    data["logistics_verified"] = True
    with pytest.raises(ValidationError):
        TripDraftSpecificationV1.model_validate(data)


def test_cli_outputs_json_result():
    proc = subprocess.run(
        [
            sys.executable, "-m", "app.assistant.planning_readiness",
            "Plan a 3 day trip to Tehran",
        ], check=True, capture_output=True, text=True
    )
    data = json.loads(proc.stdout)
    assert data["status"] == "ready_for_draft"
    assert data["draft_specification"]["duration_days"] == 3
