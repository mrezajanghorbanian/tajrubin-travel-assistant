"""Ephemeral Ed25519 keys and trusted-process release state tests."""
from datetime import date, timedelta
import hashlib
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1
from app.knowledge.signed_release import sign_catalog_release, SignatureValidationError
from app.knowledge.release_state import SQLiteReleaseState, ReleaseStateError
from app.knowledge.editorial_access import EditorialAccessService, VerifiedPrincipalV1, AuthorizationDenied
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue

TODAY = date(2026, 10, 26)


def signed(key, sequence, key_id="release-key"):
    snapshot = CatalogReleaseSnapshotV1(
        created_on=TODAY, record_count=0, records=(),
        content_sha256=hashlib.sha256(b"[]").hexdigest(),
    )
    return sign_catalog_release(
        snapshot, key_id=key_id, signer=key,
        sequence=sequence, expires_on=TODAY + timedelta(days=3),
    )


def verify_args(key):
    return dict(channel="iran", trusted_keys={"release-key": key.public_key()}, current_date=lambda: TODAY)


def test_sequence_persists_and_rejects_rollback(tmp_path):
    key = Ed25519PrivateKey.generate()
    db = tmp_path / "sequence.db"
    with SQLiteReleaseState(db) as state:
        state.accept(signed(key, 2), **verify_args(key))
        assert state.highest_sequence("iran") == 2
    with SQLiteReleaseState(db) as state:
        with pytest.raises(SignatureValidationError, match="older"):
            state.accept(signed(key, 1), **verify_args(key))
        assert state.highest_sequence("iran") == 2
        state.accept(signed(key, 3), **verify_args(key))
        assert state.highest_sequence("iran") == 3


def test_invalid_signature_does_not_advance_counter(tmp_path):
    key = Ed25519PrivateKey.generate()
    forged = signed(Ed25519PrivateKey.generate(), 4)
    with SQLiteReleaseState(tmp_path / "s.db") as state:
        with pytest.raises(SignatureValidationError, match="signature invalid"):
            state.accept(forged, **verify_args(key))
        assert state.highest_sequence("iran") is None


def test_same_signed_release_is_idempotent_but_conflict_fails(tmp_path):
    key = Ed25519PrivateKey.generate()
    release = signed(key, 2)
    with SQLiteReleaseState(tmp_path / "s.db") as state:
        state.accept(release, **verify_args(key))
        state.accept(release, **verify_args(key))
        different = sign_catalog_release(
            release.snapshot, key_id="release-key", signer=key,
            sequence=2, expires_on=TODAY + timedelta(days=2),
        )
        with pytest.raises(ReleaseStateError, match="Conflicting"):
            state.accept(different, **verify_args(key))
        assert state.highest_sequence("iran") == 2


def test_unknown_channel_and_expired_release(tmp_path):
    key = Ed25519PrivateKey.generate()
    with SQLiteReleaseState(tmp_path / "s.db") as state:
        with pytest.raises(ReleaseStateError, match="channel"):
            state.accept(signed(key, 1), channel="iran'; DROP TABLE x", trusted_keys={"release-key":key.public_key()},current_date=lambda:TODAY)
        with pytest.raises(SignatureValidationError, match="expired"):
            state.accept(signed(key, 1), channel="iran", trusted_keys={"release-key":key.public_key()}, current_date=lambda:TODAY + timedelta(days=5))


class Verifier:
    def verify(self, value):
        if value == "publisher":
            return VerifiedPrincipalV1(subject="carol", roles=frozenset({"publisher"}))
        if value == "reviewer":
            return VerifiedPrincipalV1(subject="bob", roles=frozenset({"reviewer"}))
        raise ValueError("unauthorized")


def test_only_publisher_can_create_snapshot(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "queue.db") as queue:
        api = EditorialAccessService(queue, Verifier(), current_date=lambda:TODAY)
        with pytest.raises(AuthorizationDenied):
            api.create_release_snapshot("reviewer", maximum_records=10)
        snapshot = api.create_release_snapshot("publisher", maximum_records=10)
        assert snapshot.record_count == 0
        assert snapshot.created_on == TODAY
