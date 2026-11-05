"""Online editorial freshness gate for consuming signed catalog releases.

A correct signature proves who signed a particular set of bytes, not whether
the source claims remain approved. This optional trusted-process gate rechecks
the editorial database before exposing records to an itinerary pipeline.

It is NOT an offline revocation mechanism or a cross-database transaction.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Mapping

from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.release_protocol_v2 import (
    SignedCatalogReleaseV2,
    VerificationKey,
    verify_release_v2,
)
from app.knowledge.release_snapshot import create_editorial_release_snapshot
from app.knowledge.release_state import SQLiteReleaseState


class ReleaseConsumptionError(ValueError):
    """The release is not currently usable for trusted travel data."""


def consume_current_editorial_release(
    *,
    release: SignedCatalogReleaseV2,
    channel: str,
    trusted_keys: Mapping[str, VerificationKey],
    current_date: Callable[[], date],
    editorial: SQLiteEditorialReviewQueue,
    state: SQLiteReleaseState,
    maximum_records: int = 20,
) -> tuple:
    """Check signing integrity, current approval, and durable anti-rollback.

    The return is a tuple of approved attraction records. Source authenticity,
    real-world opening hours, and transit are NOT independently verified.

    A trusted, reachable editorial database is required for every operation.
    Concurrent editorial modifications can race between checks: callers must
    fail closed on exceptions and must not treat this as cross-database ACID.
    """
    if not isinstance(editorial, SQLiteEditorialReviewQueue):
        raise ReleaseConsumptionError("Trusted editorial database is required")
    if not isinstance(state, SQLiteReleaseState):
        raise ReleaseConsumptionError("Persistent release state is required")
    if type(maximum_records) is not int or not 2 <= maximum_records <= 50:
        raise ReleaseConsumptionError("Invalid approved catalog size cap")
    if not callable(current_date):
        raise ReleaseConsumptionError("Trusted clock required")

    today = current_date()
    if type(today) is not date:
        raise ReleaseConsumptionError("Trusted clock returned invalid date")

    verified = verify_release_v2(
        release, expected_channel=channel,
        trusted_keys=trusted_keys, current_date=lambda: today,
    )
    if verified.record_count == 0:
        raise ReleaseConsumptionError("Empty release cannot be used")

    def reviewed_records() -> tuple:
        approved = create_editorial_release_snapshot(
            editorial, created_on=today,
            maximum_records=maximum_records,
        )
        if approved.records != verified.records:
            raise ReleaseConsumptionError(
                "Published records differ from current editorial approval"
            )
        return approved.records

    records = reviewed_records()
    # Consumer-side version acceptance serializes the local monotonic
    # sequence. Editorial changes can still happen in its separate database.
    accepted = state.accept_v2(
        release, channel=channel,
        trusted_keys=trusted_keys, current_date=lambda: today,
    )
    if accepted != verified:
        raise ReleaseConsumptionError("Accepted release differs from verified data")
    # Close part of the race window. If this fails, do NOT return records;
    # the local anti-rollback counter may already have advanced.
    reviewed_records()
    return records


__all__ = ["ReleaseConsumptionError", "consume_current_editorial_release"]
