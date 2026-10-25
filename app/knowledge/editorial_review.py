"""Local editorial approval queue for public attraction records.

A submitted record is *not* published. Publishing requires a separate reviewer
identity, an explicit approval decision and source-date checks. This local
library does not authenticate identities or independently verify URLs; only
wire it into an authenticated service after a separate security review.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.attraction_catalog import AttractionRecordV1


Decision = Literal["approve", "reject"]
State = Literal["pending", "approved", "rejected", "revoked"]

MAX_QUEUE_BATCH = 100
MAX_QUERY_RESULTS = 50


class EditorialWorkflowError(ValueError):
    """Rejected workflow action or invalid submission."""


class ReviewEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int
    attraction_id: str
    action: Literal["submit", "approve", "reject", "revoke"]
    actor: str
    recorded_on: date
    record_sha256: str
    reason: str


def _nonempty(value: str, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise EditorialWorkflowError(f"{label} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise EditorialWorkflowError(f"{label} must contain 1–{maximum} characters")
    return normalized


def _digest(record_json: str) -> str:
    return hashlib.sha256(record_json.encode("utf-8")).hexdigest()


def _reviewable(record: AttractionRecordV1, on_date: date) -> bool:
    # Reject *all* non-production source claims, including unused fixtures.
    return all(
        source.kind != "fixture"
        and source.observed_at <= on_date <= source.valid_through
        for source in record.sources
    )


class SQLiteEditorialReviewQueue:
    """SQLite approval workflow: submit → independent review → publish/revoke.

    Not an identity provider, permission engine, or tamper-proof ledger.
    Uses the caller's actor string; callers MUST be trusted or authenticated.
    Production publishing must access only approved(), never staging tables.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path))
        self._connection.row_factory = sqlite3.Row
        try:
            with self._connection:
                self._connection.executescript(
                    """
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE IF NOT EXISTS editorial_submissions (
                        attraction_id TEXT PRIMARY KEY,
                        record_json TEXT NOT NULL,
                        record_sha256 TEXT NOT NULL,
                        state TEXT NOT NULL CHECK (
                            state IN ('pending','approved','rejected','revoked')
                        ),
                        submitter TEXT NOT NULL,
                        submitted_on TEXT NOT NULL,
                        reviewed_on TEXT,
                        reviewer TEXT
                    );
                    CREATE TABLE IF NOT EXISTS editorial_events (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        attraction_id TEXT NOT NULL,
                        action TEXT NOT NULL CHECK (
                            action IN ('submit','approve','reject','revoke')
                        ),
                        actor TEXT NOT NULL,
                        recorded_on TEXT NOT NULL,
                        record_sha256 TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        FOREIGN KEY (attraction_id)
                          REFERENCES editorial_submissions(attraction_id)
                    );
                    CREATE INDEX IF NOT EXISTS editorial_status_idx
                        ON editorial_submissions (state, attraction_id);
                    """
                )
        except Exception:
            self._connection.close()
            raise

    def __enter__(self) -> "SQLiteEditorialReviewQueue":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def submit(
        self,
        records: tuple[AttractionRecordV1, ...],
        *,
        submitted_by: str,
        submitted_on: date,
    ) -> int:
        """Immutable candidate intake. Atomic; never publishes or overwrites."""
        actor = _nonempty(submitted_by, "submitter", 100)
        if not isinstance(submitted_on, date):
            raise EditorialWorkflowError("submitted_on must be a date")
        if len(records) > MAX_QUEUE_BATCH:
            raise EditorialWorkflowError("Submission exceeds bounded batch limit")
        if len({record.attraction_id for record in records}) != len(records):
            raise EditorialWorkflowError("Duplicate attraction IDs in submission")
        if any(source.kind == "fixture" for r in records for source in r.sources):
            raise EditorialWorkflowError("Synthetic fixtures cannot enter editorial queue")
        entries = tuple((r.attraction_id, r.model_dump_json()) for r in records)
        try:
            with self._connection:
                for attraction_id, payload in entries:
                    checksum = _digest(payload)
                    self._connection.execute(
                        """INSERT INTO editorial_submissions
                        (attraction_id, record_json, record_sha256, state,
                         submitter, submitted_on)
                        VALUES (?, ?, ?, 'pending', ?, ?)""",
                        (attraction_id, payload, checksum, actor, submitted_on.isoformat()),
                    )
                    self._connection.execute(
                        """INSERT INTO editorial_events
                        (attraction_id, action, actor, recorded_on, record_sha256, reason)
                        VALUES (?, 'submit', ?, ?, ?, 'Submitted for review')""",
                        (attraction_id, actor, submitted_on.isoformat(), checksum),
                    )
        except sqlite3.IntegrityError as exc:
            raise EditorialWorkflowError(
                "Submission ID already exists; transaction rolled back"
            ) from exc
        return len(entries)

    def pending(self, *, limit: int = 20) -> tuple[AttractionRecordV1, ...]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_QUERY_RESULTS:
            raise EditorialWorkflowError("Invalid pending result limit")
        rows = self._connection.execute(
            """SELECT record_json FROM editorial_submissions
               WHERE state = 'pending' ORDER BY attraction_id LIMIT ?""",
            (limit,),
        ).fetchall()
        return tuple(AttractionRecordV1.model_validate_json(r["record_json"]) for r in rows)

    def decide(
        self,
        attraction_id: str,
        *,
        reviewed_by: str,
        reviewed_on: date,
        decision: Decision,
        reason: str,
    ) -> State:
        """Require independent reviewer and eligible evidence for publication."""
        key = _nonempty(attraction_id, "attraction_id", 100)
        actor = _nonempty(reviewed_by, "reviewer", 100)
        comment = _nonempty(reason, "review reason", 500)
        if not isinstance(reviewed_on, date):
            raise EditorialWorkflowError("reviewed_on must be a date")
        if decision not in ("approve", "reject"):
            raise EditorialWorkflowError("Unsupported review decision")

        with self._connection:
            record = self._connection.execute(
                "SELECT * FROM editorial_submissions WHERE attraction_id = ?",
                (key,),
            ).fetchone()
            if record is None:
                raise EditorialWorkflowError("Unknown attraction submission")
            if record["state"] != "pending":
                raise EditorialWorkflowError("Only pending submissions may be reviewed")
            if actor.casefold() == record["submitter"].casefold():
                raise EditorialWorkflowError("Self-approval and self-review are prohibited")
            if reviewed_on < date.fromisoformat(record["submitted_on"]):
                raise EditorialWorkflowError("Review cannot predate submission")
            if _digest(record["record_json"]) != record["record_sha256"]:
                raise EditorialWorkflowError("Submitted record fingerprint mismatch")

            if decision == "approve":
                parsed = AttractionRecordV1.model_validate_json(record["record_json"])
                if not _reviewable(parsed, reviewed_on):
                    raise EditorialWorkflowError(
                        "Source metadata is fixture-only, future-dated or expired"
                    )
                state: State = "approved"
            else:
                state = "rejected"

            self._connection.execute(
                """UPDATE editorial_submissions
                SET state = ?, reviewed_on = ?, reviewer = ?
                WHERE attraction_id = ?""",
                (state, reviewed_on.isoformat(), actor, key),
            )
            self._connection.execute(
                """INSERT INTO editorial_events
                (attraction_id, action, actor, recorded_on, record_sha256, reason)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    key, decision, actor, reviewed_on.isoformat(),
                    record["record_sha256"], comment,
                ),
            )
        return state

    def revoke(
        self,
        attraction_id: str,
        *,
        revoked_by: str,
        revoked_on: date,
        reason: str,
    ) -> None:
        key = _nonempty(attraction_id, "attraction_id", 100)
        actor = _nonempty(revoked_by, "reviewer", 100)
        comment = _nonempty(reason, "revocation reason", 500)
        if not isinstance(revoked_on, date):
            raise EditorialWorkflowError("revoked_on must be a date")
        with self._connection:
            row = self._connection.execute(
                "SELECT * FROM editorial_submissions WHERE attraction_id = ?",
                (key,),
            ).fetchone()
            if row is None or row["state"] != "approved":
                raise EditorialWorkflowError("Only approved submissions can be revoked")
            if actor.casefold() == row["submitter"].casefold():
                raise EditorialWorkflowError("Submitter cannot revoke own record")
            if revoked_on < date.fromisoformat(row["reviewed_on"]):
                raise EditorialWorkflowError("Revocation cannot predate approval")
            self._connection.execute(
                "UPDATE editorial_submissions SET state = 'revoked' WHERE attraction_id = ?",
                (key,),
            )
            self._connection.execute(
                """INSERT INTO editorial_events
                (attraction_id, action, actor, recorded_on, record_sha256, reason)
                VALUES (?, 'revoke', ?, ?, ?, ?)""",
                (
                    key, actor, revoked_on.isoformat(),
                    row["record_sha256"], comment,
                ),
            )

    def approved(
        self,
        *,
        as_of: date,
        country_code: str | None = None,
        city: str | None = None,
        limit: int = 20,
    ) -> tuple[AttractionRecordV1, ...]:
        """Editorially approved, non-revoked, date-valid source claims only.

        This does not establish real-world truth or live opening hours.
        """
        if not isinstance(as_of, date):
            raise EditorialWorkflowError("as_of must be a date")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_QUERY_RESULTS:
            raise EditorialWorkflowError("Invalid approved result limit")
        if country_code is not None and (
            len(country_code) != 2 or not country_code.isascii()
            or not country_code.isalpha() or country_code != country_code.upper()
        ):
            raise EditorialWorkflowError("Invalid country_code filter")
        if city is not None and (not isinstance(city, str) or not city.strip() or len(city) > 120):
            raise EditorialWorkflowError("Invalid city filter")

        # Bounded page over approved records *after* all filters. We do not
        # apply SQL LIMIT before filtering out expired records.
        rows = self._connection.execute(
            """SELECT record_json, reviewed_on FROM editorial_submissions
               WHERE state = 'approved' AND reviewed_on <= ?
               ORDER BY attraction_id""",
            (as_of.isoformat(),),
        ).fetchall()
        visible: list[AttractionRecordV1] = []
        for row in rows:
            if _digest(row["record_json"]) != row["record_sha256"]:
                raise EditorialWorkflowError("Approved record fingerprint mismatch")
            record = AttractionRecordV1.model_validate_json(row["record_json"])
            if country_code is not None and record.country_code != country_code:
                continue
            if city is not None and record.city.casefold() != city.strip().casefold():
                continue
            if not _reviewable(record, as_of):
                continue
            visible.append(record)
            if len(visible) == limit:
                break
        return tuple(visible)

    def approved_by_ids(
        self,
        attraction_ids: tuple[str, ...],
        *,
        as_of: date,
    ) -> tuple[AttractionRecordV1, ...]:
        """Retrieve exactly requested, currently approved IDs in input order.

        Recheck source metadata and content digests at every read. Unapproved,
        revoked or stale entries are omitted: the caller must reject a
        partial response instead of silently downgrading a requested plan.
        """
        if not isinstance(as_of, date):
            raise EditorialWorkflowError("as_of must be a date")
        if len(attraction_ids) > MAX_QUEUE_BATCH:
            raise EditorialWorkflowError("Requested ID count exceeds limit")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 100
            for item in attraction_ids
        ):
            raise EditorialWorkflowError("Invalid attraction ID")
        if len(set(attraction_ids)) != len(attraction_ids):
            raise EditorialWorkflowError("Duplicate attraction IDs")
        if not attraction_ids:
            return ()

        placeholders = ",".join("?" for _ in attraction_ids)
        rows = self._connection.execute(
            """SELECT attraction_id, record_json, record_sha256
               FROM editorial_submissions
               WHERE state = 'approved' AND reviewed_on <= ?
               AND attraction_id IN (""" + placeholders + ")",
            (as_of.isoformat(), *attraction_ids),
        ).fetchall()
        available: dict[str, AttractionRecordV1] = {}
        for row in rows:
            if _digest(row["record_json"]) != row["record_sha256"]:
                raise EditorialWorkflowError("Approved record fingerprint mismatch")
            record = AttractionRecordV1.model_validate_json(row["record_json"])
            if record.attraction_id != row["attraction_id"]:
                raise EditorialWorkflowError("Approved record ID mismatch")
            if _reviewable(record, as_of):
                available[row["attraction_id"]] = record
        return tuple(
            available[identifier]
            for identifier in attraction_ids
            if identifier in available
        )

    def audit(self, attraction_id: str) -> tuple[ReviewEventV1, ...]:
        key = _nonempty(attraction_id, "attraction_id", 100)
        rows = self._connection.execute(
            """SELECT * FROM editorial_events
               WHERE attraction_id = ? ORDER BY sequence""",
            (key,),
        ).fetchall()
        return tuple(
            ReviewEventV1(
                sequence=r["sequence"], attraction_id=r["attraction_id"],
                action=r["action"], actor=r["actor"],
                recorded_on=date.fromisoformat(r["recorded_on"]),
                record_sha256=r["record_sha256"], reason=r["reason"],
            )
            for r in rows
        )


__all__ = [
    "EditorialWorkflowError", "ReviewEventV1", "SQLiteEditorialReviewQueue",
]
