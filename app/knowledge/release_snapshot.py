"""Immutable, content-addressed export of *currently approved* catalog data.

Manifest hashes detect accidental modifications but are not signatures.
Consumer must independently validate publishing authority and revocations.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge.attraction_catalog import AttractionRecordV1
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue


class ReleaseSnapshotError(ValueError):
    """An invalid snapshot, digest, or inconsistent release attempt."""


def _canonical(records: tuple[AttractionRecordV1, ...]) -> bytes:
    return json.dumps(
        [record.model_dump(mode="json") for record in records],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


class CatalogReleaseSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_version: Literal["1.0"] = "1.0"
    created_on: date
    records: tuple[AttractionRecordV1, ...] = Field(max_length=500)
    record_count: int = Field(ge=0, le=500)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trust_state: Literal["editorial_only"] = "editorial_only"
    authenticity_verified: Literal[False] = False

    @model_validator(mode="after")
    def verify_digest(self) -> "CatalogReleaseSnapshotV1":
        if self.record_count != len(self.records):
            raise ValueError("release record count mismatch")
        if tuple(sorted(r.attraction_id for r in self.records)) != tuple(
            r.attraction_id for r in self.records
        ):
            raise ValueError("release records must be sorted by ID")
        if len(set(r.attraction_id for r in self.records)) != len(self.records):
            raise ValueError("duplicate release records")
        if hashlib.sha256(_canonical(self.records)).hexdigest() != self.content_sha256:
            raise ValueError("release content hash mismatch")
        return self


def create_editorial_release_snapshot(
    queue: SQLiteEditorialReviewQueue,
    *,
    created_on: date,
    maximum_records: int = 500,
) -> CatalogReleaseSnapshotV1:
    """Export only editorially approved claims, failing closed on overflow."""
    if type(created_on) is not date:
        raise ReleaseSnapshotError("A trusted release date is required")
    if type(maximum_records) is not int or not 1 <= maximum_records <= 500:
        raise ReleaseSnapshotError("Invalid release size cap")
    # The approved() API is paged at 50. Refuse large catalogs for this v1
    # exporter rather than accidentally publishing a truncated snapshot.
    if maximum_records > 50:
        raise ReleaseSnapshotError("Version 1 supports at most 50 approved records")
    records = queue.approved(as_of=created_on, limit=maximum_records)
    if len(records) == maximum_records:
        raise ReleaseSnapshotError(
            "Release might be truncated; choose smaller batch or pagination"
        )
    ordered = tuple(sorted(records, key=lambda record: record.attraction_id))
    checksum = hashlib.sha256(_canonical(ordered)).hexdigest()
    return CatalogReleaseSnapshotV1(
        created_on=created_on, records=ordered,
        record_count=len(ordered), content_sha256=checksum,
    )


__all__ = [
    "CatalogReleaseSnapshotV1", "ReleaseSnapshotError",
    "create_editorial_release_snapshot",
]
