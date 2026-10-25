"""Ed25519-signed catalog release envelopes (offline, no stored private keys).

The caller owns key custody and trusted time. Signing does not independently
validate the underlying attraction claims or confer publishing authority.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import date
from typing import Callable, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1


class SignatureValidationError(ValueError):
    """Release authenticity or freshness could not be established."""


class ReleaseSigner(Protocol):
    def sign(self, message: bytes) -> bytes:
        ...


class TrustedEd25519Key(Protocol):
    def verify(self, signature: bytes, message: bytes) -> None:
        ...


def _payload(*, snapshot: CatalogReleaseSnapshotV1, key_id: str, expires_on: date, sequence: int) -> bytes:
    return json.dumps(
        {
            "domain": "tajrubin.catalog.release.ed25519.v1",
            "key_id": key_id,
            "sequence": sequence,
            "expires_on": expires_on.isoformat(),
            "snapshot": snapshot.model_dump(mode="json"),
        },
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


class SignedCatalogReleaseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    envelope_version: Literal["1.0"] = "1.0"
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
    sequence: int = Field(ge=1, le=2**63 - 1)
    expires_on: date
    snapshot: CatalogReleaseSnapshotV1
    signature_b64: str = Field(min_length=88, max_length=88)

    @model_validator(mode="after")
    def date_and_signature_shape(self) -> "SignedCatalogReleaseV1":
        if self.expires_on < self.snapshot.created_on:
            raise ValueError("Release expiry precedes creation")
        try:
            decoded = base64.b64decode(self.signature_b64, validate=True)
        except ValueError as exc:
            raise ValueError("Invalid signature encoding") from exc
        if len(decoded) != 64:
            raise ValueError("Invalid Ed25519 signature size")
        return self


def sign_catalog_release(
    snapshot: CatalogReleaseSnapshotV1,
    *,
    key_id: str,
    signer: ReleaseSigner,
    sequence: int,
    expires_on: date,
) -> SignedCatalogReleaseV1:
    """Sign complete canonical release metadata and nested catalog records."""
    if not isinstance(snapshot, CatalogReleaseSnapshotV1):
        raise SignatureValidationError("Validated snapshot required")
    if not callable(getattr(signer, "sign", None)):
        raise SignatureValidationError("External signer required")
    if expires_on < snapshot.created_on:
        raise SignatureValidationError("Release cannot expire before creation")
    # Validate key/sequence before passing inputs to the signer.
    stub = SignedCatalogReleaseV1(
        key_id=key_id, sequence=sequence, expires_on=expires_on,
        snapshot=snapshot, signature_b64=base64.b64encode(b"\x00" * 64).decode("ascii"),
    )
    message = _payload(
        snapshot=snapshot, key_id=stub.key_id,
        sequence=stub.sequence, expires_on=stub.expires_on,
    )
    signature = signer.sign(message)
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise SignatureValidationError("Signer did not return an Ed25519 signature")
    return stub.model_copy(update={
        "signature_b64": base64.b64encode(signature).decode("ascii")
    })


def verify_catalog_release(
    release: SignedCatalogReleaseV1,
    *,
    trusted_keys: Mapping[str, TrustedEd25519Key],
    current_date: Callable[[], date],
    minimum_sequence: int = 1,
) -> CatalogReleaseSnapshotV1:
    """Fail closed on absent trust, invalid signature, expiry or replay.

    Callers MUST persist the highest accepted sequence in trusted storage;
    the function does not maintain an anti-replay database.
    """
    if not isinstance(release, SignedCatalogReleaseV1):
        raise SignatureValidationError("Validated signed release required")
    today = current_date()
    if type(today) is not date:
        raise SignatureValidationError("Trusted current date required")
    if type(minimum_sequence) is not int or minimum_sequence < 1:
        raise SignatureValidationError("Invalid minimum release sequence")
    if not release.snapshot.created_on <= today <= release.expires_on:
        raise SignatureValidationError("Release is future-dated or expired")
    if release.sequence < minimum_sequence:
        raise SignatureValidationError("Release is older than accepted sequence")
    key = trusted_keys.get(release.key_id)
    if key is None:
        raise SignatureValidationError("Unknown or revoked release signing key")
    if not callable(getattr(key, "verify", None)):
        raise SignatureValidationError("Unusable trusted public key")
    try:
        key.verify(
            base64.b64decode(release.signature_b64, validate=True),
            _payload(
                snapshot=release.snapshot, key_id=release.key_id,
                sequence=release.sequence, expires_on=release.expires_on,
            ),
        )
    except Exception as exc:
        raise SignatureValidationError("Catalog release signature invalid") from exc
    return release.snapshot


__all__ = [
    "SignatureValidationError", "SignedCatalogReleaseV1",
    "sign_catalog_release", "verify_catalog_release",
]
