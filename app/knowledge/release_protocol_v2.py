"""Channel-bound Ed25519 catalog release protocol v2.

Unlike legacy v1, the release channel is included in the signed payload.
Publisher credentials, signing keys and trusted time are provided externally.
No network request, secret persistence or production identity provider.
"""
from __future__ import annotations

import base64
import json
from datetime import date
from typing import Callable, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1


class ReleaseV2Error(ValueError):
    """Signed release could not be trusted."""


class SigningKey(Protocol):
    def sign(self, data: bytes) -> bytes: ...


class VerificationKey(Protocol):
    def verify(self, signature: bytes, data: bytes) -> None: ...


def _payload(
    snapshot: CatalogReleaseSnapshotV1,
    channel: str,
    key_id: str,
    sequence: int,
    expires_on: date,
) -> bytes:
    return json.dumps(
        {
            "domain": "tajrubin.catalog.release.ed25519.v2",
            "channel": channel,
            "key_id": key_id,
            "sequence": sequence,
            "expires_on": expires_on.isoformat(),
            "snapshot": snapshot.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class SignedCatalogReleaseV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    envelope_version: Literal["2.0"] = "2.0"
    algorithm: Literal["Ed25519"] = "Ed25519"
    channel: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    key_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
    sequence: int = Field(ge=1, le=2**63 - 1)
    expires_on: date
    snapshot: CatalogReleaseSnapshotV1
    signature_b64: str = Field(min_length=88, max_length=88)

    @model_validator(mode="after")
    def validate_envelope(self) -> "SignedCatalogReleaseV2":
        if self.expires_on < self.snapshot.created_on:
            raise ValueError("Expiry cannot precede creation")
        try:
            binary = base64.b64decode(self.signature_b64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid signature encoding") from exc
        if len(binary) != 64:
            raise ValueError("Invalid Ed25519 signature length")
        return self


def sign_release_v2(
    snapshot: CatalogReleaseSnapshotV1,
    *,
    channel: str,
    key_id: str,
    sequence: int,
    expires_on: date,
    signer: SigningKey,
) -> SignedCatalogReleaseV2:
    if not isinstance(snapshot, CatalogReleaseSnapshotV1):
        raise ReleaseV2Error("Validated snapshot required")
    if not callable(getattr(signer, "sign", None)):
        raise ReleaseV2Error("External signer required")
    stub = SignedCatalogReleaseV2(
        channel=channel, key_id=key_id, sequence=sequence,
        expires_on=expires_on, snapshot=snapshot,
        signature_b64=base64.b64encode(bytes(64)).decode("ascii"),
    )
    binary = signer.sign(
        _payload(snapshot, stub.channel, stub.key_id, stub.sequence, stub.expires_on)
    )
    if not isinstance(binary, bytes) or len(binary) != 64:
        raise ReleaseV2Error("Signer returned invalid signature")
    return SignedCatalogReleaseV2(
        channel=stub.channel, key_id=stub.key_id, sequence=stub.sequence,
        expires_on=stub.expires_on, snapshot=stub.snapshot,
        signature_b64=base64.b64encode(binary).decode("ascii"),
    )


def verify_release_v2(
    release: SignedCatalogReleaseV2,
    *,
    expected_channel: str,
    trusted_keys: Mapping[str, VerificationKey],
    current_date: Callable[[], date],
    minimum_sequence: int = 1,
) -> CatalogReleaseSnapshotV1:
    if not isinstance(release, SignedCatalogReleaseV2):
        raise ReleaseV2Error("Validated v2 release required")
    if release.channel != expected_channel:
        raise ReleaseV2Error("Release channel mismatch")
    today = current_date()
    if type(today) is not date:
        raise ReleaseV2Error("Trusted current date required")
    if not release.snapshot.created_on <= today <= release.expires_on:
        raise ReleaseV2Error("Release not currently valid")
    if type(minimum_sequence) is not int or minimum_sequence < 1:
        raise ReleaseV2Error("Invalid minimum sequence")
    if release.sequence < minimum_sequence:
        raise ReleaseV2Error("Release sequence rollback")
    key = trusted_keys.get(release.key_id)
    if key is None or not callable(getattr(key, "verify", None)):
        raise ReleaseV2Error("Untrusted release key")
    # Verify before returning even if schema validation previously succeeded.
    try:
        key.verify(
            base64.b64decode(release.signature_b64, validate=True),
            _payload(
                release.snapshot, release.channel, release.key_id,
                release.sequence, release.expires_on,
            ),
        )
    except Exception as exc:
        raise ReleaseV2Error("Release signature verification failed") from exc
    return release.snapshot


__all__ = [
    "ReleaseV2Error", "SignedCatalogReleaseV2",
    "sign_release_v2", "verify_release_v2",
]
