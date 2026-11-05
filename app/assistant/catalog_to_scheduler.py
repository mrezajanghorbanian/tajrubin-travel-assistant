"""Fail-closed adapter from source-attributed attraction catalog to scheduler."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.assistant.itinerary_scheduler import OpeningWindowV1, VisitCandidateV1
from app.knowledge.attraction_catalog import AttractionRecordV1, CatalogSourceV1


class CatalogEvidenceError(ValueError):
    """A catalog record is unsupported, stale or not valid for the visit date."""


class VisitSelectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    attraction_id: str = Field(min_length=1, max_length=100)
    day_index: int = Field(ge=1, le=30)
    on_date: date


def _fresh(source: CatalogSourceV1, *, on_date: date) -> bool:
    return (
        source.kind != "fixture"
        and source.observed_at <= on_date <= source.valid_through
    )


def build_visit_candidates(
    catalog: tuple[AttractionRecordV1, ...],
    selections: tuple[VisitSelectionV1, ...],
    *,
    allow_synthetic_fixtures: bool = False,
) -> tuple[VisitCandidateV1, ...]:
    """Reject missing claims and stale evidence; preserve selection order.

    Fixture permission is only for synthetic tests/demos. It is never proof
    of real-world availability, and must never be enabled for public plans.
    """
    records = {record.attraction_id: record for record in catalog}
    if len(records) != len(catalog):
        raise CatalogEvidenceError("Duplicate attraction IDs")
    if len(selections) > 100:
        raise CatalogEvidenceError("Too many selected attractions")
    candidates: list[VisitCandidateV1] = []
    seen: set[str] = set()
    for selected in selections:
        if selected.attraction_id in seen:
            raise CatalogEvidenceError("Activity selected more than once")
        seen.add(selected.attraction_id)
        record = records.get(selected.attraction_id)
        if record is None:
            raise CatalogEvidenceError("Selected attraction is missing from catalog")
        sources = {source.source_id: source for source in record.sources}

        def require(source_id: str, *, check_date: date) -> None:
            source = sources[source_id]
            if not (_fresh(source, on_date=check_date) or (
                allow_synthetic_fixtures and source.kind == "fixture"
                and source.observed_at <= check_date <= source.valid_through
            )):
                raise CatalogEvidenceError("Missing, fixture-only or expired catalog evidence")

        require(record.location.source_id, check_date=selected.on_date)
        require(record.duration_source_id, check_date=selected.on_date)
        if record.accessibility.source_id is not None:
            require(record.accessibility.source_id, check_date=selected.on_date)

        windows = tuple(
            OpeningWindowV1(
                on_date=window.on_date, opens_at=window.opens_at,
                closes_at=window.closes_at, source_id=window.source_id,
            )
            for window in record.opening_windows
            if window.on_date == selected.on_date
        )
        if not windows:
            raise CatalogEvidenceError("No dated opening hours for selected visit day")
        for window in windows:
            require(window.source_id, check_date=selected.on_date)
        candidates.append(VisitCandidateV1(
            activity_id=record.attraction_id,
            title=record.name, city=record.city,
            day_index=selected.day_index,
            duration_minutes=record.visit_duration_minutes,
            knowledge_document_id=record.knowledge_document_id,
            opening_windows=windows,
        ))
    return tuple(candidates)


__all__ = ["CatalogEvidenceError", "VisitSelectionV1", "build_visit_candidates"]
