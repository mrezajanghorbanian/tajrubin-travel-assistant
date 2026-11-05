"""Evidence-constrained, deterministic single-city itinerary scheduler.

This is an offline *provisional* feasibility check over supplied data, NOT an
opening-hours API, route optimizer, live availability check, or booking engine.
Unknown data blocks the plan rather than being guessed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, time, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.assistant.planning_readiness import TripDraftSpecificationV1


class _Immutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class OpeningWindowV1(_Immutable):
    """One source-supplied, local-clock availability interval for a date."""

    on_date: date
    opens_at: time
    closes_at: time
    source_id: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_window(self) -> "OpeningWindowV1":
        if _minutes(self.opens_at) >= _minutes(self.closes_at):
            raise ValueError("opening window must close after it opens")
        return self


class VisitCandidateV1(_Immutable):
    activity_id: str = Field(
        min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    title: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    day_index: int = Field(ge=1, le=30)
    duration_minutes: int = Field(ge=15, le=480)
    knowledge_document_id: str = Field(min_length=1, max_length=160)
    opening_windows: tuple[OpeningWindowV1, ...] = Field(max_length=60)


class TravelTimeV1(_Immutable):
    """Directed, provided travel-time estimate; reverse direction is distinct."""

    from_activity_id: str = Field(min_length=1, max_length=100)
    to_activity_id: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(ge=0, le=720)
    source_id: str = Field(min_length=1, max_length=160)


class ScheduledVisitV1(_Immutable):
    activity_id: str
    title: str
    begins_at: time
    ends_at: time
    travel_from_previous_minutes: int | None = None
    knowledge_document_id: str
    opening_source_id: str
    travel_source_id: str | None = None


class ScheduledDayV1(_Immutable):
    day_index: int = Field(ge=1, le=30)
    on_date: date
    city: str
    visits: tuple[ScheduledVisitV1, ...] = ()


IssueCode = Literal[
    "missing_start_date", "missing_candidates", "unsupported_multicity",
    "city_mismatch", "invalid_day_assignment", "duplicate_activity",
    "duplicate_travel_edge", "missing_opening_hours", "missing_travel_time",
    "outside_opening_hours", "outside_daily_window", "date_range_conflict",
    "invalid_daily_window",
]


class PlanningIssueV1(_Immutable):
    code: IssueCode
    message: str = Field(min_length=1, max_length=300)
    day_index: int | None = None
    activity_id: str | None = None


class ItineraryScheduleV1(_Immutable):
    status: Literal["provisional", "blocked", "infeasible"]
    days: tuple[ScheduledDayV1, ...] = ()
    issues: tuple[PlanningIssueV1, ...] = ()
    verified_live: Literal[False] = False
    requires_independent_verification: Literal[True] = True
    notice: str = (
        "Based solely on supplied availability and travel-time records; "
        "opening hours, transit times, prices and access were not verified live."
    )


def _minutes(clock: time) -> int:
    return clock.hour * 60 + clock.minute


def _clock(value: int) -> time:
    return time(hour=value // 60, minute=value % 60)


def _issue(
    code: IssueCode,
    message: str,
    day_index: int | None = None,
    activity_id: str | None = None,
) -> PlanningIssueV1:
    return PlanningIssueV1(
        code=code, message=message, day_index=day_index, activity_id=activity_id
    )


def _rejected(
    status: Literal["blocked", "infeasible"],
    issues: list[PlanningIssueV1],
) -> ItineraryScheduleV1:
    # Atomic result: never offer a partial itinerary as if it were complete.
    return ItineraryScheduleV1(status=status, issues=tuple(issues))


def build_provisional_itinerary(
    specification: TripDraftSpecificationV1,
    candidates: tuple[VisitCandidateV1, ...],
    travel_times: tuple[TravelTimeV1, ...],
    *,
    day_begins_at: time = time(9, 0),
    day_ends_at: time = time(18, 0),
) -> ItineraryScheduleV1:
    """Schedule *ordered, preselected* activities only when all inputs suffice.

    Candidate order within a day is preserved; no route optimization occurs.
    Travel times must be supplied for every adjacent ordered pair. Validated
    numeric feasibility does not imply live-world correctness.
    """
    issues: list[PlanningIssueV1] = []
    if not 0 <= _minutes(day_begins_at) < _minutes(day_ends_at) < 1440:
        return _rejected(
            "blocked", [_issue("invalid_daily_window", "Daily time window is invalid.")]
        )
    if len(specification.destinations) != 1:
        issues.append(_issue(
            "unsupported_multicity",
            "This scheduling slice supports exactly one destination city.",
        ))
    if specification.dates is None:
        issues.append(_issue(
            "missing_start_date",
            "Provide a travel start date before assigning opening-hour slots.",
        ))
    if len(candidates) > 100 or len(travel_times) > 400:
        raise ValueError("Input exceeds bounded planner capacity")
    if not candidates:
        issues.append(_issue("missing_candidates", "No activity candidates were supplied."))

    candidate_ids: set[str] = set()
    grouped: dict[int, list[VisitCandidateV1]] = defaultdict(list)
    target = specification.destinations[0] if len(specification.destinations) == 1 else None
    for candidate in candidates:
        if candidate.activity_id in candidate_ids:
            issues.append(_issue(
                "duplicate_activity", "Activity is assigned more than once.",
                candidate.day_index, candidate.activity_id,
            ))
        candidate_ids.add(candidate.activity_id)
        if candidate.day_index > specification.duration_days:
            issues.append(_issue(
                "invalid_day_assignment", "Activity assigned outside trip duration.",
                candidate.day_index, candidate.activity_id,
            ))
        if target is not None and candidate.city.casefold() != target.casefold():
            issues.append(_issue(
                "city_mismatch", "Activity city does not match planned destination.",
                candidate.day_index, candidate.activity_id,
            ))
        grouped[candidate.day_index].append(candidate)

    travel_lookup: dict[tuple[str, str], TravelTimeV1] = {}
    for edge in travel_times:
        key = (edge.from_activity_id, edge.to_activity_id)
        if key in travel_lookup:
            issues.append(_issue(
                "duplicate_travel_edge", "Ambiguous duplicate directed travel-time edge."
            ))
        travel_lookup[key] = edge
    if issues:
        return _rejected("blocked", issues)

    start_date = specification.dates.start_date
    end_date = specification.dates.end_date
    if end_date is not None and (end_date - start_date).days + 1 != specification.duration_days:
        return _rejected("blocked", [_issue(
            "date_range_conflict", "Date range and trip duration disagree."
        )])

    scheduled: list[ScheduledDayV1] = []
    for index in range(1, specification.duration_days + 1):
        this_day = start_date + timedelta(days=index - 1)
        entries = grouped.get(index, [])
        if not entries:
            return _rejected("blocked", [_issue(
                "missing_candidates", "No candidate activities for this trip day.", index
            )])

        end_of_previous = _minutes(day_begins_at)
        previous_id: str | None = None
        visits: list[ScheduledVisitV1] = []
        for candidate in entries:
            leg: TravelTimeV1 | None = None
            if previous_id is not None:
                leg = travel_lookup.get((previous_id, candidate.activity_id))
                if leg is None:
                    return _rejected("blocked", [_issue(
                        "missing_travel_time",
                        "Directed travel-time evidence is missing between consecutive stops.",
                        index, candidate.activity_id,
                    )])

            windows = sorted(
                (w for w in candidate.opening_windows if w.on_date == this_day),
                key=lambda w: (_minutes(w.opens_at), _minutes(w.closes_at)),
            )
            if not windows:
                return _rejected("blocked", [_issue(
                    "missing_opening_hours",
                    "No source-supplied opening window exists for this date.",
                    index, candidate.activity_id,
                )])

            arrival = end_of_previous + (
                leg.duration_minutes if leg is not None else 0
            )
            chosen: tuple[int, int, OpeningWindowV1] | None = None
            for window in windows:
                beginning = max(arrival, _minutes(window.opens_at))
                ending = beginning + candidate.duration_minutes
                if (
                    ending <= _minutes(window.closes_at)
                    and ending <= _minutes(day_ends_at)
                ):
                    chosen = beginning, ending, window
                    break
            if chosen is None:
                issue_code: IssueCode = (
                    "outside_daily_window"
                    if arrival + candidate.duration_minutes > _minutes(day_ends_at)
                    else "outside_opening_hours"
                )
                return _rejected("infeasible", [_issue(
                    issue_code,
                    "The supplied activity order cannot fit in the given time windows.",
                    index, candidate.activity_id,
                )])

            beginning, ending, window = chosen
            visits.append(ScheduledVisitV1(
                activity_id=candidate.activity_id,
                title=candidate.title,
                begins_at=_clock(beginning),
                ends_at=_clock(ending),
                travel_from_previous_minutes=(
                    leg.duration_minutes if leg is not None else None
                ),
                knowledge_document_id=candidate.knowledge_document_id,
                opening_source_id=window.source_id,
                travel_source_id=leg.source_id if leg is not None else None,
            ))
            end_of_previous = ending
            previous_id = candidate.activity_id

        scheduled.append(ScheduledDayV1(
            day_index=index, on_date=this_day,
            city=target or "", visits=tuple(visits),
        ))
    return ItineraryScheduleV1(status="provisional", days=tuple(scheduled))


__all__ = [
    "OpeningWindowV1", "VisitCandidateV1", "TravelTimeV1",
    "ScheduledVisitV1", "ScheduledDayV1", "PlanningIssueV1",
    "ItineraryScheduleV1", "build_provisional_itinerary",
]
