"""Channel-bound release protocol v2, using ephemeral in-memory signing keys."""
import hashlib
from datetime import date, timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError
from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1
from app.knowledge.release_protocol_v2 import (
    ReleaseV2Error, SignedCatalogReleaseV2, sign_release_v2, verify_release_v2,
)

TODAY=date(2026,10,26)

def sample():
    return CatalogReleaseSnapshotV1(
        created_on=TODAY, records=(), record_count=0,
        content_sha256=hashlib.sha256(b"[]").hexdigest(),
    )

def signed(channel="iran", sequence=1):
    key=Ed25519PrivateKey.generate()
    rel=sign_release_v2(
        sample(), channel=channel, key_id="test-ed25519",
        sequence=sequence, expires_on=TODAY+timedelta(days=2), signer=key,
    )
    return key,rel

def check(key,rel,channel="iran",today=TODAY,minimum=1):
    return verify_release_v2(
        rel,expected_channel=channel,
        trusted_keys={"test-ed25519":key.public_key()},
        current_date=lambda:today,minimum_sequence=minimum,
    )

def test_v2_round_trip():
    key,rel=signed()
    assert check(key,rel)==sample()

def test_cross_channel_replay_rejected():
    key,rel=signed()
    with pytest.raises(ReleaseV2Error, match="channel"):
        check(key,rel,channel="other")

def test_channel_tampering_invalidates_signature():
    key,rel=signed()
    modified=rel.model_copy(update={"channel":"other"})
    with pytest.raises(ReleaseV2Error,match="signature"):
        check(key,modified,channel="other")

def test_sequence_tampering_invalidates_signature():
    key,rel=signed()
    with pytest.raises(ReleaseV2Error,match="signature"):
        check(key,rel.model_copy(update={"sequence":2}))

def test_unknown_key_fails():
    _,rel=signed()
    with pytest.raises(ReleaseV2Error,match="Untrusted"):
        verify_release_v2(
            rel,expected_channel="iran",trusted_keys={},
            current_date=lambda:TODAY,
        )

def test_expired_and_future_dated_fail():
    key,rel=signed()
    with pytest.raises(ReleaseV2Error,match="not currently valid"):
        check(key,rel,today=TODAY+timedelta(days=3))
    with pytest.raises(ReleaseV2Error,match="not currently valid"):
        check(key,rel,today=TODAY-timedelta(days=1))

def test_rollback_fails():
    key,rel=signed(sequence=4)
    with pytest.raises(ReleaseV2Error,match="rollback"):
        check(key,rel,minimum=5)

def test_malformed_channel_and_signature_rejected():
    _,rel=signed()
    payload=rel.model_dump()
    payload["channel"]="bad/channel"
    with pytest.raises(ValidationError):
        SignedCatalogReleaseV2.model_validate(payload)
    payload=rel.model_dump()
    payload["signature_b64"]="invalid"
    with pytest.raises(ValidationError):
        SignedCatalogReleaseV2.model_validate(payload)

def test_wrong_public_key_fails():
    _,rel=signed()
    with pytest.raises(ReleaseV2Error,match="signature"):
        check(Ed25519PrivateKey.generate(),rel)
