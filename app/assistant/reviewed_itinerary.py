"""Fail-closed boundary: approved attraction records → provisional schedule.

Approval is checked at the request's review date and source claims are checked
again at each visit date. This is not an authentication or live-routing service.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.assistant.catalog_to_scheduler import (
    CatalogEvidenceError,
    VisitSelectionV1,
    build_visit_candidates,
)
from app.assistant.itinerary_scheduler import (
    ItineraryScheduleV1,
    TravelTimeV1,
    build_provisional_itinerary,
)
from app.assistant.planning_readiness import TripDraftSpecificationV1
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue


class PublicationGateError(ValueError):
    """A requested attraction is not authorized as reviewed, usable evidence."""


class PlanningPublicationRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    review_as_of: date
    selections: tuple[VisitSelectionV1, ...]
    travel_times: tuple[TravelTimeV1, ...] = ()


def build_reviewed_itinerary(
    queue: SQLiteEditorialReviewQueue,
    specification: TripDraftSpecificationV1,
    request: PlanningPublicationRequestV1,
) -> ItineraryScheduleV1:
    """Read exact reviewed IDs, validate each source and schedule atomically.

    Travel-time inputs remain caller-supplied estimates with source labels;
    this gateway does not authenticate route evidence.
    """
    if not request.selections:
        raise PublicationGateError("No attraction selections")
    if len(request.selections) > 100:
        raise PublicationGateError("Selection capacity exceeded")
    if specification.dates is None:
        raise PublicationGateError("Explicit trip dates required")
    first = specification.dates.start_date

    for selection in request.selections:
        if selection.day_index > specification.duration_days:
            raise PublicationGateError("Visit day outside trip duration")
        expected = first.toordinal() + selection.day_index - 1
        if selection.on_date.toordinal() != expected:
            raise PublicationGateError("Selection date does not match assigned trip day")

    identifiers = tuple(selection.attraction_id for selection in request.selections)
    try:
        approved = queue.approved_by_ids(identifiers, as_of=request.review_as_of)
    except ValueError as exc:
        raise PublicationGateError("Editorial evidence lookup failed") from exc
    if tuple(record.attraction_id for record in approved) != identifiers:
        raise PublicationGateError("Selection contains pending, rejected, revoked or stale records")

    try:
        candidates = build_visit_candidates(approved, request.selections)
    except CatalogEvidenceError as exc:
        raise PublicationGateError("Visit-date source evidence missing or expired") from exc

    return build_provisional_itinerary(
        specification, candidates, request.travel_times
    )


__all__ = [
    "PublicationGateError", "PlanningPublicationRequestV1",
    "build_reviewed_itinerary",
]
