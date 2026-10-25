"""Persistent anti-rollback state for signed releases.

SQLite serializes version acceptance with BEGIN IMMEDIATE. The database must
be protected from unauthorized edits/rollback; it is not tamper-proof.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Mapping
from datetime import date

from app.knowledge.signed_release import (
    SignedCatalogReleaseV1, TrustedEd25519Key,
    SignatureValidationError, verify_catalog_release,
)
from app.knowledge.release_snapshot import CatalogReleaseSnapshotV1


class ReleaseStateError(ValueError):
    """Release sequence conflict or untrusted storage."""


class SQLiteReleaseState:
    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        try:
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS release_state (
                    channel TEXT PRIMARY KEY,
                    highest_sequence INTEGER NOT NULL CHECK(highest_sequence >= 1),
                    release_signature TEXT NOT NULL
                )
            """)
        except Exception:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def accept(
        self,
        release: SignedCatalogReleaseV1,
        *,
        channel: str,
        trusted_keys: Mapping[str, TrustedEd25519Key],
        current_date: Callable[[], date],
    ) -> CatalogReleaseSnapshotV1:
        if not isinstance(channel, str) or not 1 <= len(channel) <= 80 or not all(
            c.isascii() and (c.isalnum() or c in "._-") for c in channel
        ):
            raise ReleaseStateError("Invalid release channel")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            previous = self._db.execute(
                "SELECT highest_sequence, release_signature FROM release_state WHERE channel=?",
                (channel,),
            ).fetchone()
            floor = previous[0] if previous else 1
            snapshot = verify_catalog_release(
                release, trusted_keys=trusted_keys,
                current_date=current_date, minimum_sequence=floor,
            )
            if previous and release.sequence == previous[0]:
                if previous[1] != release.signature_b64:
                    raise ReleaseStateError("Conflicting release at existing sequence")
            else:
                self._db.execute(
                    """INSERT INTO release_state(channel,highest_sequence,release_signature)
                    VALUES(?,?,?) ON CONFLICT(channel) DO UPDATE SET
                    highest_sequence=excluded.highest_sequence,
                    release_signature=excluded.release_signature""",
                    (channel, release.sequence, release.signature_b64),
                )
            self._db.execute("COMMIT")
            return snapshot
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def highest_sequence(self, channel: str) -> int | None:
        row = self._db.execute(
            "SELECT highest_sequence FROM release_state WHERE channel=?", (channel,)
        ).fetchone()
        return row[0] if row else None


__all__ = ["SQLiteReleaseState", "ReleaseStateError"]
