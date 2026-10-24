"""Strict readiness gate before *draft* itinerary generation.

Converts typed intent into a bounded planning specification; never invents
route travel times, opening hours, live prices or attraction availability.
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.assistant.traveler_intent_v2 import (
    TravelBudgetV2,
    TravelDatesV2,
    TravelerIntentV2,
    analyze_traveler_intent_v2,
)

Blocker = Literal[
    "destinations", "duration_days", "travel_dates", "budget",
    "route_order", "duration_conflict",
]
Status = Literal["ready_for_draft", "needs_clarification", "not_planning"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TripDraftSpecificationV1(_Frozen):
    """Intent-derived *draft input*, NOT a validated or bookable itinerary."""

    destinations: tuple[str, ...] = Field(min_length=1, max_length=12)
    origin: str | None = None
    route_order_explicit: bool = False
    duration_days: int = Field(ge=1, le=30)
    duration_source: Literal["explicit", "inclusive_iso_date_range"]
    dates: TravelDatesV2 | None = None
    party_size: int | None = Field(default=None, ge=1, le=30)
    interests: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    pace: str | None = None
    budget: TravelBudgetV2 | None = None
    logistics_verified: Literal[False] = False


class PlanningReadinessV1(_Frozen):
    status: Status
    intent: TravelerIntentV2
    blockers: tuple[Blocker, ...] = ()
    clarification_question: str | None = None
    draft_specification: TripDraftSpecificationV1 | None = None


_QUESTIONS_FA = {
    "destinations": "به کدام مقصد یا مقصدها می‌خواهید سفر کنید؟",
    "duration_days": "سفر شما چند روز طول می‌کشد؟",
    "travel_dates": "تاریخ سفر را با مشخص‌کردن تقویم و روز دقیق می‌گویید؟",
    "budget": "بودجه سفر چقدر است و واحد پول آن چیست؟",
    "route_order": "ترتیب بازدید از این شهرها را مشخص می‌کنید؟",
    "duration_conflict": "مدت سفر با بازه تاریخ نمی‌خواند؛ کدام‌یک صحیح است؟",
}
_QUESTIONS_EN = {
    "destinations": "Which destination or destinations will you visit?",
    "duration_days": "How many days is your trip?",
    "travel_dates": "What are the exact travel dates and calendar?",
    "budget": "What is your trip budget and currency?",
    "route_order": "In which order do you want to visit these cities?",
    "duration_conflict": "The stated duration conflicts with the date range. Which is correct?",
}
_CURRENCYLESS_BUDGET = re.compile(
    r"(?:\bbudget\b|\bspend\b|\bunder\b|بودجه|سقف هزینه)"
)


def _date_duration(dates: TravelDatesV2 | None) -> int | None:
    if dates is None or dates.end_date is None:
        return None
    return (dates.end_date - dates.start_date).days + 1


def assess_planning_readiness(
    intent: TravelerIntentV2,
) -> PlanningReadinessV1:
    """Fail closed on conflicting facts; allow drafts without live validation."""
    if intent.base.intent_type != "trip_planning":
        return PlanningReadinessV1(status="not_planning", intent=intent)

    blockers: list[Blocker] = list(intent.unresolved_fields)
    days = intent.base.duration_days
    derived_days = _date_duration(intent.travel_dates)
    source: Literal["explicit", "inclusive_iso_date_range"] = "explicit"

    if days is None and derived_days is not None:
        days = derived_days
        source = "inclusive_iso_date_range"

    if (
        derived_days is not None
        and intent.base.duration_days is not None
        and derived_days != intent.base.duration_days
    ):
        blockers.append("duration_conflict")

    if days is not None and not 1 <= days <= 30:
        blockers.append("duration_days")
        days = None

    if len(intent.destinations) > 1 and not intent.route_order_explicit:
        blockers.append("route_order")

    # If a budget is explicitly mentioned but we cannot safely parse it,
    # ask for its amount/currency rather than dropping the restriction.
    normalized = intent.base.request.casefold()
    if (
        _CURRENCYLESS_BUDGET.search(normalized)
        and intent.budget is None
        and "budget" not in blockers
    ):
        blockers.append("budget")

    if not intent.destinations and "destinations" not in blockers:
        blockers.append("destinations")
    if days is None and "duration_days" not in blockers:
        blockers.append("duration_days")

    # Deterministic order = ask a single, highest-impact question.
    priority: tuple[Blocker, ...] = (
        "destinations", "duration_days", "travel_dates", "duration_conflict",
        "budget", "route_order",
    )
    blockers_tuple = tuple(code for code in priority if code in blockers)
    persian = re.search(r"[\u0600-\u06ff]", intent.base.request) is not None
    if blockers_tuple:
        questions = _QUESTIONS_FA if persian else _QUESTIONS_EN
        return PlanningReadinessV1(
            status="needs_clarification",
            intent=intent,
            blockers=blockers_tuple,
            clarification_question=questions[blockers_tuple[0]],
        )

    if days is None:
        raise ValueError("Trip duration must be resolved before drafting")
    return PlanningReadinessV1(
        status="ready_for_draft",
        intent=intent,
        draft_specification=TripDraftSpecificationV1(
            destinations=intent.destinations,
            origin=intent.origin,
            route_order_explicit=intent.route_order_explicit,
            duration_days=days,
            duration_source=source,
            dates=intent.travel_dates,
            party_size=intent.base.party_size,
            interests=intent.base.interests,
            avoid=intent.base.avoid,
            pace=intent.base.pace,
            budget=intent.budget,
        ),
    )


def analyze_planning_request(text: str) -> PlanningReadinessV1:
    return assess_planning_readiness(analyze_traveler_intent_v2(text))


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline safe trip-draft readiness")
    parser.add_argument("request", help="Persian or English travel request")
    args = parser.parse_args()
    print(analyze_planning_request(args.request).model_dump_json(indent=2))


if __name__ == "__main__":
    main()


__all__ = [
    "TripDraftSpecificationV1", "PlanningReadinessV1",
    "assess_planning_readiness", "analyze_planning_request",
]
