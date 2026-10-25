"""Catalog contracts and safety-gated scheduler integration; all data synthetic."""
from datetime import date, time

import pytest
from pydantic import ValidationError

from app.knowledge.attraction_catalog import (
    CatalogSourceV1, GeoPointV1, AccessibilityV1,
    DatedOpeningV1, AttractionRecordV1,
)
from app.assistant.catalog_to_scheduler import (
    CatalogEvidenceError, VisitSelectionV1, build_visit_candidates,
)
from app.assistant.planning_readiness import analyze_planning_request
from app.assistant.itinerary_scheduler import build_provisional_itinerary

DAY = date(2026, 11, 3)


def attraction(kind="fixture", through=date(2026, 11, 30)):
    src = CatalogSourceV1(
        source_id="sample.source", title="Synthetic fixture" if kind == "fixture" else "Test source",
        kind=kind, url=None if kind == "fixture" else "https://example.org/attraction",
        observed_at=date(2026, 10, 1), valid_through=through,
    )
    return AttractionRecordV1(
        attraction_id="sample.museum", knowledge_document_id="sample.doc",
        name="Synthetic museum", country_code="IR", city="Tehran",
        location=GeoPointV1(latitude=35.0, longitude=51.0, source_id=src.source_id),
        visit_duration_minutes=60, duration_source_id=src.source_id,
        accessibility=AccessibilityV1(wheelchair_access="unknown"),
        opening_windows=(DatedOpeningV1(
            on_date=DAY, opens_at=time(9), closes_at=time(17), source_id=src.source_id
        ),), sources=(src,),
    )


def selected():
    return (VisitSelectionV1(attraction_id="sample.museum", day_index=1, on_date=DAY),)


def test_fixture_is_blocked_by_default():
    with pytest.raises(CatalogEvidenceError, match="fixture-only"):
        build_visit_candidates((attraction(),), selected())


def test_fixture_opt_in_is_only_for_tests():
    candidates = build_visit_candidates(
        (attraction(),), selected(), allow_synthetic_fixtures=True
    )
    assert candidates[0].activity_id == "sample.museum"
    assert candidates[0].opening_windows[0].source_id == "sample.source"


def test_expired_claim_is_not_accepted():
    with pytest.raises(CatalogEvidenceError, match="expired"):
        build_visit_candidates(
            (attraction("official", through=date(2026, 10, 31)),), selected()
        )


def test_official_source_claim_can_be_scheduled_but_never_called_live_verified():
    candidates = build_visit_candidates((attraction("official"),), selected())
    specification = analyze_planning_request(
        "Plan a 1 day trip to Tehran on 2026-11-03"
    ).draft_specification
    result = build_provisional_itinerary(specification, candidates, ())
    assert result.status == "provisional"
    assert result.verified_live is False
    assert result.days[0].visits[0].knowledge_document_id == "sample.doc"


def test_unknown_selection_is_rejected():
    with pytest.raises(CatalogEvidenceError, match="missing"):
        build_visit_candidates((), selected())


def test_missing_opening_windows_are_rejected():
    bad = attraction("official").model_copy(update={"opening_windows": ()})
    with pytest.raises(CatalogEvidenceError, match="opening hours"):
        build_visit_candidates((bad,), selected())


def test_source_reference_must_exist():
    with pytest.raises(ValidationError, match="provenance"):
        attraction().model_copy(update={"duration_source_id": "other"}).model_validate(
            attraction().model_dump() | {"duration_source_id": "other"}
        )


def test_invalid_geocoordinates_are_rejected():
    with pytest.raises(ValidationError):
        GeoPointV1(latitude=110, longitude=51, source_id="sample.source")


def test_accessibility_claim_needs_source():
    with pytest.raises(ValidationError):
        AccessibilityV1(wheelchair_access="yes")


def test_non_https_source_is_rejected():
    with pytest.raises(ValidationError):
        CatalogSourceV1(
            source_id="a", title="test", kind="official",
            url="http://example.org", observed_at=DAY, valid_through=DAY
        )


def test_duplicate_catalog_ids_fail():
    with pytest.raises(CatalogEvidenceError, match="Duplicate"):
        build_visit_candidates((attraction(), attraction()), selected())


def test_no_silent_accessibility_certification():
    a = attraction("editorial")
    assert a.accessibility.wheelchair_access == "unknown"
