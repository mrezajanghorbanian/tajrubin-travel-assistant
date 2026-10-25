"""Publisher-authorized, transactional issuance of channel-bound catalog releases.

Only signed envelopes are stored. Signing keys, identity credentials and key
material stay with external dependencies. SQLite transactions protect issuance
sequence and record persistence, NOT cross-database editorial publication or
durable key custody.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Mapping

from app.knowledge.editorial_access import EditorialAccessService
from app.knowledge.release_protocol_v2 import (
    ReleaseV2Error,
    SignedCatalogReleaseV2,
    SigningKey,
    VerificationKey,
    sign_release_v2,
    verify_release_v2,
)

MAX_SEQUENCE = 2**63 - 1
_CHANNEL = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}\Z")
_KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class ReleaseIssuanceError(ValueError):
    """Release was not durably issued; fix the request and retry."""


def _identifier(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ReleaseIssuanceError(f"Invalid {label}")
    return value


class SQLiteCatalogReleaseIssuer:
    """Use one SQLite issuer ledger for all writers of a given channel.

    IMPORTANT: approval data may live in a separate database. Therefore the
    ledger transaction is atomic, but the editorial read + signing operation
    is not a cross-database atomic transaction. A production pipeline needs
    publisher isolation, coordinated revocation and an external signing KMS.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._db = sqlite3.connect(str(database_path), timeout=10, isolation_level=None)
        try:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS catalog_issuances (
                    channel TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence > 0),
                    request_id TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    PRIMARY KEY(channel, sequence),
                    UNIQUE(channel, request_id)
                )"""
            )
        except Exception:
            self._db.close()
            raise

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SQLiteCatalogReleaseIssuer":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def issue(
        self,
        access: EditorialAccessService,
        credential: str,
        *,
        channel: str,
        key_id: str,
        request_id: str,
        signer: SigningKey,
        trusted_keys: Mapping[str, VerificationKey],
        lifetime_days: int = 7,
        maximum_records: int = 20,
    ) -> SignedCatalogReleaseV2:
        """Authorize, sign, verify, and commit a version without gaps on error.

        Idempotency is scoped to channel + request_id. Retries require the same
        current snapshot, key and expiration policy and a valid publisher.
        """
        _identifier(channel, _CHANNEL, "channel")
        _identifier(key_id, _KEY_ID, "key ID")
        _identifier(request_id, _REQUEST, "idempotency request ID")
        if type(lifetime_days) is not int or not 1 <= lifetime_days <= 30:
            raise ReleaseIssuanceError("Invalid release lifetime")
        if type(maximum_records) is not int or not 2 <= maximum_records <= 50:
            raise ReleaseIssuanceError("Invalid catalog size cap")
        if not isinstance(access, EditorialAccessService):
            raise ReleaseIssuanceError("Trusted publisher access boundary required")
        if trusted_keys.get(key_id) is None:
            raise ReleaseIssuanceError("Publisher key is not registered as trusted")
        if not callable(getattr(signer, "sign", None)):
            raise ReleaseIssuanceError("External signer is required")

        self._db.execute("BEGIN IMMEDIATE")
        try:
            # This method verifies the publisher identity and obtains a trusted
            # date. Never derive actor, date or rights from user-provided data.
            snapshot = access.create_release_snapshot(
                credential, maximum_records=maximum_records
            )
            if snapshot.record_count == 0:
                raise ReleaseIssuanceError("Empty catalog cannot be published")
            expires_on = snapshot.created_on + timedelta(days=lifetime_days)

            previous = self._db.execute(
                """SELECT sequence, key_id, envelope_json
                   FROM catalog_issuances
                   WHERE channel=? AND request_id=?""",
                (channel, request_id),
            ).fetchone()
            if previous is not None:
                old = SignedCatalogReleaseV2.model_validate_json(previous[2])
                if (
                    old.sequence != previous[0]
                    or old.channel != channel
                    or old.key_id != previous[1]
                    or old.key_id != key_id
                    or old.snapshot != snapshot
                    or old.expires_on != expires_on
                ):
                    raise ReleaseIssuanceError("Idempotency request conflicts with prior release")
                verify_release_v2(
                    old, expected_channel=channel, trusted_keys=trusted_keys,
                    current_date=lambda: snapshot.created_on,
                    minimum_sequence=old.sequence,
                )
                self._db.execute("COMMIT")
                return old

            row = self._db.execute(
                "SELECT MAX(sequence) FROM catalog_issuances WHERE channel=?",
                (channel,),
            ).fetchone()
            last_sequence = row[0] if row[0] is not None else 0
            if last_sequence >= MAX_SEQUENCE:
                raise ReleaseIssuanceError("Release sequence exhausted")
            sequence = last_sequence + 1
            release = sign_release_v2(
                snapshot, channel=channel, key_id=key_id,
                sequence=sequence, expires_on=expires_on, signer=signer,
            )
            # Do not commit unverified output from an external signing service.
            verify_release_v2(
                release, expected_channel=channel, trusted_keys=trusted_keys,
                current_date=lambda: snapshot.created_on,
                minimum_sequence=sequence,
            )
            self._db.execute(
                """INSERT INTO catalog_issuances
                   (channel, sequence, request_id, key_id, envelope_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    channel, sequence, request_id, key_id,
                    release.model_dump_json(),
                ),
            )
            self._db.execute("COMMIT")
            return release
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def last_issued_sequence(self, channel: str) -> int | None:
        _identifier(channel, _CHANNEL, "channel")
        row = self._db.execute(
            "SELECT MAX(sequence) FROM catalog_issuances WHERE channel=?",
            (channel,),
        ).fetchone()
        return row[0]


__all__ = ["SQLiteCatalogReleaseIssuer", "ReleaseIssuanceError"]
