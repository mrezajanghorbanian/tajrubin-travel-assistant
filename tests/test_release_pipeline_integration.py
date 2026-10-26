"""Real component integration: review → issue → verify → durable acceptance.

All attractions, dates and source URLs below are synthetic test fixtures.
No production identities, keys, tourism facts or live services are used.
"""
from datetime import date, time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from app.knowledge.attraction_catalog import (
    AttractionRecordV1, CatalogSourceV1, DatedOpeningV1, GeoPointV1,
)
from app.knowledge.editorial_access import (
    AuthorizationDenied, EditorialAccessService, VerifiedPrincipalV1,
)
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.release_issuer import (
    ReleaseIssuanceError, SQLiteCatalogReleaseIssuer,
)
from app.knowledge.release_protocol_v2 import (
    ReleaseV2Error, SignedCatalogReleaseV2,
)
from app.knowledge.release_state import SQLiteReleaseState

TODAY = date(2026, 10, 26)
DESTINATION_DATE = date(2026, 11, 3)


class TestVerifier:
    """Not an actual auth provider: only for isolated, offline testing."""

    def verify(self, credential):
        principals = {
            "contributor": ("alice", "contributor"),
            "reviewer": ("bob", "reviewer"),
            "publisher": ("carol", "publisher"),
        }
        if credential not in principals:
            raise ValueError("unauthorized")
        name, role = principals[credential]
        return VerifiedPrincipalV1(subject=name, roles=frozenset({role}))


def attraction(name="synthetic.gallery"):
    source = CatalogSourceV1(
        source_id="synthetic.source", title="Synthetic source (not checked)",
        kind="editorial", url="https://example.org/fixture-only",
        observed_at=date(2026, 10, 1),
        valid_through=date(2026, 12, 31),
    )
    return AttractionRecordV1(
        attraction_id=name,
        knowledge_document_id="synthetic.knowledge",
        name="Synthetic Gallery",
        country_code="IR",
        city="Tehran",
        location=GeoPointV1(latitude=35.0, longitude=51.0, source_id="synthetic.source"),
        visit_duration_minutes=60,
        duration_source_id="synthetic.source",
        opening_windows=(
            DatedOpeningV1(
                on_date=DESTINATION_DATE, opens_at=time(9), closes_at=time(17),
                source_id="synthetic.source",
            ),
        ),
        sources=(source,),
    )


def setup_approved(queue):
    api = EditorialAccessService(
        queue, TestVerifier(), current_date=lambda: TODAY
    )
    api.submit("contributor", (attraction(),))
    api.review("reviewer", "synthetic.gallery",
               decision="approve", reason="Fixture exercise only")
    return api


def issuance(issuer, api, key, request_id="req-one", signer=None):
    return issuer.issue(
        api, "publisher", channel="iran", key_id="ephemeral-key",
        request_id=request_id, signer=signer if signer is not None else key,
        trusted_keys={"ephemeral-key": key.public_key()},
        lifetime_days=7, maximum_records=10,
    )


def accept(state, signed, key, channel="iran"):
    return state.accept_v2(
        signed, channel=channel,
        trusted_keys={"ephemeral-key": key.public_key()},
        current_date=lambda: TODAY,
    )


def test_approved_record_full_pipeline_survives_restart(tmp_path):
    signing_key = Ed25519PrivateKey.generate()
    review_path = tmp_path / "review.sqlite3"
    issuance_path = tmp_path / "issuer.sqlite3"
    acceptance_path = tmp_path / "accepted.sqlite3"

    with SQLiteEditorialReviewQueue(review_path) as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(issuance_path) as issuer:
            signed = issuance(issuer, api, signing_key)
            assert signed.sequence == 1
            assert signed.snapshot.record_count == 1
            assert signed.snapshot.records[0].attraction_id == "synthetic.gallery"

    with SQLiteReleaseState(acceptance_path) as client:
        snapshot = accept(client, signed, signing_key)
        assert snapshot == signed.snapshot
        assert client.highest_sequence("iran") == 1

    with SQLiteReleaseState(acceptance_path) as client:
        assert accept(client, signed, signing_key) == signed.snapshot
        assert client.highest_sequence("iran") == 1


def test_pending_record_never_issued(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = EditorialAccessService(
            queue, TestVerifier(), current_date=lambda: TODAY
        )
        api.submit("contributor", (attraction(),))
        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            with pytest.raises(ReleaseIssuanceError, match="Empty"):
                issuance(issuer, api, key)
            assert issuer.last_issued_sequence("iran") is None


def test_signer_side_effect_revocation_aborts_atomic_issue(tmp_path):
    """A revocation during a slow signing call must be caught on final recheck."""
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = setup_approved(queue)

        class RevokingSigner:
            def sign(self, message: bytes) -> bytes:
                api.revoke(
                    "reviewer", "synthetic.gallery",
                    reason="Source retracted during signing"
                )
                return key.sign(message)

        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            with pytest.raises(ReleaseIssuanceError, match="changed during signing"):
                issuance(issuer, api, key, signer=RevokingSigner())
            assert issuer.last_issued_sequence("iran") is None


def test_signer_side_effect_new_approval_aborts_issue(tmp_path):
    """A changed approved set must invalidate the signer input snapshot."""
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = setup_approved(queue)

        class ApprovingSigner:
            def sign(self, message: bytes) -> bytes:
                api.submit("contributor", (attraction("synthetic.second"),))
                api.review(
                    "reviewer", "synthetic.second",
                    decision="approve", reason="Newly included record"
                )
                return key.sign(message)

        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            with pytest.raises(ReleaseIssuanceError, match="changed during signing"):
                issuance(issuer, api, key, signer=ApprovingSigner())
            assert issuer.last_issued_sequence("iran") is None


def test_wrong_key_does_not_create_issuer_or_consumer_state(tmp_path):
    signing_key = Ed25519PrivateKey.generate()
    wrong_key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            with pytest.raises(ReleaseV2Error, match="signature"):
                issuance(issuer, api, signing_key, signer=wrong_key)
            assert issuer.last_issued_sequence("iran") is None
        with SQLiteReleaseState(tmp_path / "accepted.db") as consumer:
            assert consumer.highest_sequence("iran") is None


def test_cross_channel_replay_does_not_advance_counter(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            signed = issuance(issuer, api, key)
    with SQLiteReleaseState(tmp_path / "consumer.db") as state:
        with pytest.raises(ReleaseV2Error, match="channel"):
            accept(state, signed, key, channel="europe")
        assert state.highest_sequence("europe") is None
        assert state.highest_sequence("iran") is None


def test_payload_mutation_detected_before_consumer_acceptance(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            signed = issuance(issuer, api, key)
    payload = signed.model_dump(mode="json")
    payload["snapshot"]["records"][0]["name"] = "Tampered title"
    with pytest.raises(ValidationError, match="hash"):
        SignedCatalogReleaseV2.model_validate(payload)
    with SQLiteReleaseState(tmp_path / "consumer.db") as state:
        assert state.highest_sequence("iran") is None


def test_unauthorized_publisher_never_issues(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path / "review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path / "issuer.db") as issuer:
            with pytest.raises(AuthorizationDenied):
                issuer.issue(
                    api, "reviewer", channel="iran", key_id="ephemeral-key",
                    request_id="req-forbidden", signer=key,
                    trusted_keys={"ephemeral-key": key.public_key()},
                    maximum_records=10,
                )
            assert issuer.last_issued_sequence("iran") is None
