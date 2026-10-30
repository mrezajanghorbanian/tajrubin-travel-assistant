"""Traveler-facing planning preview composition (offline, fail closed).

This is a thin vertical slice, not a travel recommendation model or real-time
itinerary generator. It does not infer attractions, hours or travel times.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from typing import Callable, Literal, Mapping

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
from app.assistant.planning_readiness import (
    PlanningReadinessV1,
    analyze_planning_request,
)
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.release_consumer import consume_current_editorial_release
from app.knowledge.release_protocol_v2 import SignedCatalogReleaseV2, VerificationKey
from app.knowledge.release_state import SQLiteReleaseState


PreviewStatus = Literal[
    "not_planning",
    "needs_clarification",
    "needs_visit_date",
    "unsupported_multicity",
    "needs_activity_selection",
    "needs_source_release",
    "invalid_selection",
    "evidence_rejected",
    "blocked",
    "infeasible",
    "provisional",
]


class TripPreviewV1(BaseModel):
    """A safe, serializable result; nothing here confirms live availability."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: PreviewStatus
    readiness: PlanningReadinessV1
    schedule: ItineraryScheduleV1 | None = None
    feedback: str
    source_document_ids: tuple[str, ...] = ()
    live_verified: Literal[False] = False


def preview_trip_request(
    text: str,
    *,
    selections: tuple[VisitSelectionV1, ...] = (),
    travel_times: tuple[TravelTimeV1, ...] = (),
    release: SignedCatalogReleaseV2 | None = None,
    channel: str = "iran",
    trusted_keys: Mapping[str, VerificationKey] | None = None,
    current_date: Callable[[], date] | None = None,
    editorial: SQLiteEditorialReviewQueue | None = None,
    state: SQLiteReleaseState | None = None,
) -> TripPreviewV1:
    """Bridge request parsing, trusted catalog release and dated scheduling.

    Every required planning fact must be explicit. A signed release and an
    editor-approved dataset are necessary but not sufficient evidence of
    real-world truth. Selection and directed travel edges must be supplied.
    """
    readiness = analyze_planning_request(text)

    def result(status: PreviewStatus, feedback: str, schedule=None, document_ids=()):
        return TripPreviewV1(
            status=status,
            readiness=readiness,
            schedule=schedule,
            feedback=feedback,
            source_document_ids=tuple(document_ids),
        )

    if readiness.status == "not_planning":
        return result("not_planning", "This request is not an itinerary planning request.")
    if readiness.status != "ready_for_draft":
        return result(
            "needs_clarification",
            readiness.clarification_question or "More travel details are required.",
        )

    spec = readiness.draft_specification
    if spec is None:
        return result("needs_clarification", "Trip details must be resolved.")
    if len(spec.destinations) != 1:
        return result(
            "unsupported_multicity",
            "Dated intercity routing is not supported by this preview.",
        )
    if spec.dates is None:
        return result(
            "needs_visit_date",
            "Provide the exact travel date (YYYY-MM-DD) for opening-hours checks.",
        )
    if not selections:
        return result(
            "needs_activity_selection",
            "Select sourced attractions for every day; activities are never invented.",
        )

    if len(selections) > 100 or len(travel_times) > 400:
        return result("invalid_selection", "Too many visit or routing inputs.")
    if len({item.attraction_id for item in selections}) != len(selections):
        return result("invalid_selection", "An attraction was selected more than once.")

    for item in selections:
        if item.day_index > spec.duration_days:
            return result("invalid_selection", "Activity day exceeds trip length.")
        expected = spec.dates.start_date.toordinal() + item.day_index - 1
        if item.on_date.toordinal() != expected:
            return result("invalid_selection", "Activity date does not match trip day.")

    if (
        release is None or trusted_keys is None or current_date is None
        or editorial is None or state is None
    ):
        return result(
            "needs_source_release",
            "A trusted, signed and currently approved attraction catalog is required.",
        )

    try:
        approved = consume_current_editorial_release(
            release=release, channel=channel, trusted_keys=trusted_keys,
            current_date=current_date, editorial=editorial, state=state,
        )
        candidates = build_visit_candidates(approved, selections)
    except (ValueError, sqlite3.Error) as exc:
        # Do not reveal raw database, identity or key-provider internals.
        return result(
            "evidence_rejected",
            "The signed attraction evidence is unavailable, stale or invalid.",
        )

    scheduled = build_provisional_itinerary(spec, candidates, travel_times)
    if scheduled.status != "provisional":
        return result(
            scheduled.status,
            "The selected activities cannot be scheduled with the supplied evidence.",
            scheduled,
        )
    return result(
        "provisional",
        "Provisional itinerary only. Hours, routes, access and prices require "
        "independent up-to-date verification.",
        scheduled,
        tuple(visit.knowledge_document_id for day in scheduled.days for visit in day.visits),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline traveler request-to-trip preview (never invents live data)"
    )
    parser.add_argument("request", help="Persian or English travel request")
    args = parser.parse_args()
    # Without a trusted catalog and explicit selections, this CLI explains
    # what the product still needs instead of pretending to plan a real trip.
    print(preview_trip_request(args.request).model_dump_json(indent=2))


if __name__ == "__main__":
    main()


__all__ = ["TripPreviewV1", "preview_trip_request"]
