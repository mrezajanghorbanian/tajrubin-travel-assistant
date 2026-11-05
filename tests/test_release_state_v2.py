"""Persistent v2 release acceptance, synthetic signatures only."""
import hashlib
from datetime import date, timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1
from app.knowledge.release_protocol_v2 import sign_release_v2, ReleaseV2Error
from app.knowledge.release_state import SQLiteReleaseState, ReleaseStateError
TODAY=date(2026,10,26)

def release(key, sequence=1, channel="iran", expires=3):
    snap=CatalogReleaseSnapshotV1(
        created_on=TODAY, records=(), record_count=0,
        content_sha256=hashlib.sha256(b"[]").hexdigest(),
    )
    return sign_release_v2(
        snap,channel=channel,key_id="test",sequence=sequence,
        expires_on=TODAY+timedelta(days=expires),signer=key,
    )

def arguments(key, channel="iran"):
    return dict(channel=channel,trusted_keys={"test":key.public_key()},current_date=lambda:TODAY)

def test_v2_persists_sequence_and_rejects_rollback(tmp_path):
    key=Ed25519PrivateKey.generate()
    db=tmp_path/"state.db"
    with SQLiteReleaseState(db) as state:
        state.accept_v2(release(key,2),**arguments(key))
        assert state.highest_sequence("iran")==2
    with SQLiteReleaseState(db) as state:
        with pytest.raises(ReleaseV2Error,match="rollback"):
            state.accept_v2(release(key,1),**arguments(key))
        state.accept_v2(release(key,3),**arguments(key))
        assert state.highest_sequence("iran")==3

def test_v2_cross_channel_replay_never_advances_other_channel(tmp_path):
    key=Ed25519PrivateKey.generate()
    with SQLiteReleaseState(tmp_path/"state.db") as state:
        with pytest.raises(ReleaseV2Error,match="channel"):
            state.accept_v2(release(key,2,"iran"),**arguments(key,"europe"))
        assert state.highest_sequence("europe") is None

def test_v2_invalid_signature_does_not_commit(tmp_path):
    signer=Ed25519PrivateKey.generate()
    verifier=Ed25519PrivateKey.generate()
    with SQLiteReleaseState(tmp_path/"state.db") as state:
        with pytest.raises(ReleaseV2Error,match="signature"):
            state.accept_v2(release(signer),**arguments(verifier))
        assert state.highest_sequence("iran") is None

def test_v2_same_release_idempotent_conflicts_blocked(tmp_path):
    key=Ed25519PrivateKey.generate()
    original=release(key,2)
    with SQLiteReleaseState(tmp_path/"state.db") as state:
        state.accept_v2(original,**arguments(key))
        state.accept_v2(original,**arguments(key))
        with pytest.raises(ReleaseStateError,match="Conflicting"):
            state.accept_v2(release(key,2,expires=2),**arguments(key))
        assert state.highest_sequence("iran")==2
