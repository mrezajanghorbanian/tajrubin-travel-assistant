"""Traveler request-to-preview, using synthetic release data only."""
from datetime import date
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.assistant.trip_preview import preview_trip_request
from app.assistant.catalog_to_scheduler import VisitSelectionV1
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.release_issuer import SQLiteCatalogReleaseIssuer
from app.knowledge.release_state import SQLiteReleaseState
from tests.test_release_pipeline_integration import TODAY, DESTINATION_DATE, setup_approved, issuance


def request():
    return "Plan a 1 day trip to Tehran on 2026-11-03"


def selection(day=DESTINATION_DATE):
    return (VisitSelectionV1(attraction_id="synthetic.gallery",day_index=1,on_date=day),)


def test_missing_destination_asks_for_clarification():
    result=preview_trip_request("Plan a 3 day trip")
    assert result.status=="needs_clarification"
    assert result.schedule is None


def test_unrelated_question_is_not_a_planning_response():
    result=preview_trip_request("Tell me about Tehran museums")
    assert result.status=="not_planning"


def test_missing_date_never_invents_hours():
    result=preview_trip_request("Plan a 1 day trip to Tehran")
    assert result.status=="needs_visit_date"
    assert result.live_verified is False


def test_missing_attractions_never_invents_stops():
    result=preview_trip_request(request())
    assert result.status=="needs_activity_selection"


def test_no_signed_source_release_is_explicit():
    result=preview_trip_request(request(),selections=selection())
    assert result.status=="needs_source_release"


def test_selection_date_mismatch_fails_before_catalog_read():
    result=preview_trip_request(request(),selections=selection(date(2026,11,4)))
    assert result.status=="invalid_selection"


def test_multicity_is_not_misrepresented_as_supported():
    result=preview_trip_request("Plan a 3 day trip to Tehran then Shiraz on 2026-11-03")
    assert result.status=="unsupported_multicity"


def test_signed_approved_fixture_flows_into_provisional_itinerary(tmp_path):
    key=Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api=setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issuer.db") as issuer:
            release=issuance(issuer,api,key)
        with SQLiteReleaseState(tmp_path/"accepted.db") as state:
            result=preview_trip_request(
                request(),selections=selection(),release=release,
                trusted_keys={"ephemeral-key":key.public_key()},
                current_date=lambda:TODAY,editorial=queue,state=state,
            )
            assert result.status=="provisional"
            assert result.schedule.days[0].visits[0].activity_id=="synthetic.gallery"
            assert result.source_document_ids==("synthetic.knowledge",)
            assert result.live_verified is False


def test_revoked_source_is_not_shown_as_plan(tmp_path):
    key=Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api=setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issuer.db") as issuer:
            release=issuance(issuer,api,key)
        api.revoke("reviewer","synthetic.gallery",reason="Withdrawn")
        with SQLiteReleaseState(tmp_path/"accepted.db") as state:
            result=preview_trip_request(
                request(),selections=selection(),release=release,
                trusted_keys={"ephemeral-key":key.public_key()},
                current_date=lambda:TODAY,editorial=queue,state=state,
            )
            assert result.status=="evidence_rejected"
            assert result.schedule is None
            assert state.highest_sequence("iran") is None


def test_cli_reports_missing_selection_without_network():
    import json
    import subprocess
    import sys
    run=subprocess.run(
        [sys.executable,"-m","app.assistant.trip_preview",request()],
        capture_output=True,text=True,check=True,
    )
    payload=json.loads(run.stdout)
    assert payload["status"]=="needs_activity_selection"
    assert payload["live_verified"] is False
