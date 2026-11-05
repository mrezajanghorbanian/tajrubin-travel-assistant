"""Release boundary regression tests with wholly synthetic claim fixtures."""
from datetime import date, time
import pytest

from app.assistant.planning_readiness import analyze_planning_request
from app.assistant.catalog_to_scheduler import VisitSelectionV1
from app.assistant.reviewed_itinerary import (
    PlanningPublicationRequestV1, PublicationGateError, build_reviewed_itinerary,
)
from app.knowledge.attraction_catalog import (
    AttractionRecordV1, CatalogSourceV1, GeoPointV1, DatedOpeningV1,
)
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue, EditorialWorkflowError

REVIEW = date(2026, 10, 26)
VISIT = date(2026, 11, 3)


def attraction(expiry=date(2026, 12, 31)):
    source = CatalogSourceV1(
        source_id="fixture.reference", title="Synthetic editorial test claim",
        kind="editorial", url="https://example.org/synthetic",
        observed_at=date(2026, 10, 1), valid_through=expiry,
    )
    return AttractionRecordV1(
        attraction_id="synthetic.museum", knowledge_document_id="synthetic.knowledge",
        name="Synthetic Museum", country_code="IR", city="Tehran",
        location=GeoPointV1(latitude=35, longitude=51, source_id=source.source_id),
        visit_duration_minutes=60, duration_source_id=source.source_id,
        opening_windows=(DatedOpeningV1(
            on_date=VISIT, opens_at=time(9), closes_at=time(17),
            source_id=source.source_id,
        ),), sources=(source,),
    )


def spec():
    return analyze_planning_request(
        "Plan a 1 day trip to Tehran on 2026-11-03"
    ).draft_specification


def req(day=VISIT, review=REVIEW):
    return PlanningPublicationRequestV1(
        review_as_of=review,
        selections=(VisitSelectionV1(
            attraction_id="synthetic.museum", day_index=1, on_date=day
        ),),
    )


def approve(q, entry=None):
    q.submit((entry or attraction(),), submitted_by="alice", submitted_on=REVIEW)
    q.decide("synthetic.museum", reviewed_by="bob", reviewed_on=REVIEW,
             decision="approve", reason="Reviewed metadata")


def test_approved_record_reaches_provisional_scheduler(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q)
        outcome = build_reviewed_itinerary(q, spec(), req())
        assert outcome.status == "provisional"
        assert outcome.days[0].visits[0].activity_id == "synthetic.museum"
        assert outcome.verified_live is False


def test_pending_record_never_reaches_scheduler(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        q.submit((attraction(),), submitted_by="alice", submitted_on=REVIEW)
        with pytest.raises(PublicationGateError, match="pending"):
            build_reviewed_itinerary(q, spec(), req())


def test_rejected_record_never_reaches_scheduler(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        q.submit((attraction(),), submitted_by="alice", submitted_on=REVIEW)
        q.decide("synthetic.museum", reviewed_by="bob", reviewed_on=REVIEW,
                 decision="reject", reason="Evidence insufficient")
        with pytest.raises(PublicationGateError):
            build_reviewed_itinerary(q, spec(), req())


def test_revoked_record_never_reaches_scheduler(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q)
        q.revoke("synthetic.museum", revoked_by="bob", revoked_on=REVIEW,
                 reason="New concern")
        with pytest.raises(PublicationGateError):
            build_reviewed_itinerary(q, spec(), req())


def test_source_expired_by_visit_date_is_blocked(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q, attraction(expiry=date(2026, 10, 30)))
        with pytest.raises(PublicationGateError, match="Visit-date"):
            build_reviewed_itinerary(q, spec(), req())


def test_mismatched_trip_date_is_blocked(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q)
        with pytest.raises(PublicationGateError, match="date"):
            build_reviewed_itinerary(q, spec(), req(day=date(2026, 11, 4)))


def test_approval_is_not_backdated(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q)
        with pytest.raises(PublicationGateError):
            build_reviewed_itinerary(q, spec(), req(review=date(2026, 10, 25)))


def test_tampered_approved_payload_fails_closed(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q)
        q._connection.execute(
            "UPDATE editorial_submissions SET record_json = ? WHERE attraction_id = ?",
            ('{"not":"valid"}', "synthetic.museum"),
        )
        q._connection.commit()
        with pytest.raises(PublicationGateError, match="lookup failed"):
            build_reviewed_itinerary(q, spec(), req())
        with pytest.raises(EditorialWorkflowError, match="fingerprint"):
            q.approved(as_of=REVIEW)


def test_exact_lookup_is_bounded_and_ordered(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as q:
        approve(q)
        records = q.approved_by_ids(("synthetic.museum",), as_of=REVIEW)
        assert tuple(x.attraction_id for x in records) == ("synthetic.museum",)
        with pytest.raises(EditorialWorkflowError, match="Duplicate"):
            q.approved_by_ids(("synthetic.museum", "synthetic.museum"), as_of=REVIEW)
