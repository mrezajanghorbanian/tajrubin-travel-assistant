"""End-to-end current-editorial-release consumer tests. Synthetic data only."""
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.knowledge.editorial_review import SQLiteEditorialReviewQueue, EditorialWorkflowError
from app.knowledge.release_issuer import SQLiteCatalogReleaseIssuer
from app.knowledge.release_state import SQLiteReleaseState
from app.knowledge.release_consumer import (
    ReleaseConsumptionError, consume_current_editorial_release,
)
from app.knowledge.release_protocol_v2 import ReleaseV2Error

from tests.test_release_pipeline_integration import (
    TODAY, attraction, setup_approved, issuance,
)


def consume(queue, state, signed, key, *, channel="iran", today=TODAY):
    return consume_current_editorial_release(
        release=signed, channel=channel, editorial=queue, state=state,
        current_date=lambda: today,
        trusted_keys={"ephemeral-key": key.public_key()},
        maximum_records=10,
    )


def test_approved_signed_release_is_usable(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            records = consume(queue, state, signed, key)
            assert len(records) == 1
            assert records[0].attraction_id == "synthetic.gallery"
            assert state.highest_sequence("iran") == 1


def test_revoked_record_blocks_consumption_without_advancing_state(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        api.revoke("reviewer", "synthetic.gallery", reason="Withdrawn information")
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseConsumptionError, match="differ"):
                consume(queue, state, signed, key)
            assert state.highest_sequence("iran") is None


def test_newly_approved_record_invalidates_old_snapshot(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        api.submit("contributor", (attraction("synthetic.second"),))
        api.review(
            "reviewer", "synthetic.second", decision="approve",
            reason="New source approved",
        )
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseConsumptionError, match="differ"):
                consume(queue, state, signed, key)
            assert state.highest_sequence("iran") is None


def test_expired_signature_is_not_consumed(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseV2Error, match="not currently valid"):
                consume(queue, state, signed, key, today=TODAY + timedelta(days=8))
            assert state.highest_sequence("iran") is None


def test_cross_channel_rejected_even_when_approved(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseV2Error, match="channel"):
                consume(queue, state, signed, key, channel="other")
            assert state.highest_sequence("other") is None


def test_untrusted_key_rejected_without_state_change(tmp_path):
    signer = Ed25519PrivateKey.generate()
    other_key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, signer)
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseV2Error, match="signature"):
                consume(queue, state, signed, other_key)
            assert state.highest_sequence("iran") is None


def test_old_release_cannot_replay_after_newer_release_accepted(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            first = issuance(issuer, api, key)
            second = issuance(issuer, api, key, request_id="req-two")
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            consume(queue, state, second, key)
            with pytest.raises(ReleaseV2Error, match="rollback"):
                consume(queue, state, first, key)
            assert state.highest_sequence("iran") == 2


def test_malformed_size_limit_rejected(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseConsumptionError, match="size cap"):
                consume_current_editorial_release(
                    release=signed, channel="iran",
                    trusted_keys={"ephemeral-key":key.public_key()},
                    current_date=lambda:TODAY, editorial=queue, state=state,
                    maximum_records=0,
                )
            assert state.highest_sequence("iran") is None


def test_tampered_editorial_record_is_not_returned(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)
        queue._connection.execute(
            "UPDATE editorial_submissions SET record_json = ? WHERE attraction_id = ?",
            ('{"broken":true}', "synthetic.gallery"),
        )
        queue._connection.commit()
        with SQLiteReleaseState(tmp_path/"state.db") as state:
            with pytest.raises(EditorialWorkflowError, match="fingerprint"):
                consume(queue, state, signed, key)
            assert state.highest_sequence("iran") is None


def test_revocation_during_consumer_acceptance_returns_no_records(tmp_path):
    """Counter MAY advance on post-acceptance failure; never expose the records."""
    key = Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/"review.db") as queue:
        api = setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/"issue.db") as issuer:
            signed = issuance(issuer, api, key)

        class RevokingState(SQLiteReleaseState):
            def accept_v2(self, *args, **kwargs):
                accepted = super().accept_v2(*args, **kwargs)
                api.revoke(
                    "reviewer", "synthetic.gallery",
                    reason="Changed during consumer acceptance",
                )
                return accepted

        with RevokingState(tmp_path/"state.db") as state:
            with pytest.raises(ReleaseConsumptionError, match="differ"):
                consume(queue, state, signed, key)
            assert state.highest_sequence("iran") == 1
