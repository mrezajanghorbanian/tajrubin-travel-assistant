"""Ed25519 release signatures use ephemeral test keys, never stored credentials."""
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1
from app.knowledge.signed_release import (
    SignatureValidationError, SignedCatalogReleaseV1,
    sign_catalog_release, verify_catalog_release,
)

TODAY = date(2026, 10, 26)


def fixture():
    import hashlib
    return CatalogReleaseSnapshotV1(
        created_on=TODAY, records=(), record_count=0,
        content_sha256=hashlib.sha256(b"[]").hexdigest(),
    )


def sign(key=None, *, sequence=5):
    private = key or Ed25519PrivateKey.generate()
    release = sign_catalog_release(
        fixture(), key_id="test-key-1", signer=private,
        sequence=sequence, expires_on=TODAY + timedelta(days=7),
    )
    return private, release


def verify(release, key, *, today=TODAY, minimum=1):
    return verify_catalog_release(
        release, trusted_keys={"test-key-1": key.public_key()},
        current_date=lambda: today, minimum_sequence=minimum,
    )


def test_valid_ephemeral_signature_round_trip():
    private, release = sign()
    assert verify(release, private) == fixture()


def test_wrong_public_key_fails():
    _, release = sign()
    with pytest.raises(SignatureValidationError, match="signature invalid"):
        verify(release, Ed25519PrivateKey.generate())


def test_unknown_key_does_not_fallback():
    _, release = sign()
    with pytest.raises(SignatureValidationError, match="Unknown"):
        verify_catalog_release(
            release, trusted_keys={}, current_date=lambda: TODAY,
        )


def test_expired_release_fails():
    private, release = sign()
    with pytest.raises(SignatureValidationError, match="expired"):
        verify(release, private, today=TODAY + timedelta(days=8))


def test_future_dated_release_fails():
    private, release = sign()
    with pytest.raises(SignatureValidationError, match="future-dated"):
        verify(release, private, today=TODAY - timedelta(days=1))


def test_replay_sequence_fails():
    private, release = sign(sequence=5)
    with pytest.raises(SignatureValidationError, match="older"):
        verify(release, private, minimum=6)


def test_sequence_tamper_invalidates_signature():
    private, release = sign()
    tampered = release.model_copy(update={"sequence": 6})
    with pytest.raises(SignatureValidationError, match="signature invalid"):
        verify(tampered, private)


def test_key_id_tamper_invalidates_signature():
    private, release = sign()
    tampered = release.model_copy(update={"key_id": "different"})
    with pytest.raises(SignatureValidationError, match="signature invalid"):
        verify_catalog_release(
            tampered, trusted_keys={"different": private.public_key()},
            current_date=lambda: TODAY,
        )


def test_expiration_tamper_invalidates_signature():
    private, release = sign()
    tampered = release.model_copy(update={"expires_on": TODAY + timedelta(days=8)})
    with pytest.raises(SignatureValidationError, match="signature invalid"):
        verify(tampered, private)


def test_nested_snapshot_tamper_fails_validation():
    _, release = sign()
    payload = release.model_dump(mode="json")
    payload["snapshot"]["content_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="hash"):
        SignedCatalogReleaseV1.model_validate(payload)


def test_invalid_signer_return_rejected():
    class BrokenSigner:
        def sign(self, message):
            return b"not a signature"
    with pytest.raises(SignatureValidationError, match="Signer"):
        sign_catalog_release(
            fixture(), key_id="broken", signer=BrokenSigner(), sequence=1,
            expires_on=TODAY,
        )


def test_untrusted_clock_fails_closed():
    private, release = sign()
    with pytest.raises(SignatureValidationError, match="Trusted current date"):
        verify_catalog_release(
            release, trusted_keys={"test-key-1": private.public_key()},
            current_date=lambda: "2026-10-26",
        )


def test_revoked_key_fails_closed():
    _, release = sign()
    with pytest.raises(SignatureValidationError, match="Unknown"):
        verify_catalog_release(
            release, trusted_keys={}, current_date=lambda: TODAY,
        )
