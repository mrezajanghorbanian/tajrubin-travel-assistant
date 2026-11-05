"""Small, persistent, bounded SQLite attraction catalog.

No network activity. Catalog provenance is stored but *not* independently
authenticated; a source URL is not proof that a travel claim is correct.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

from app.knowledge.attraction_catalog import AttractionRecordV1

MAX_BATCH_RECORDS = 500
MAX_SEARCH_LIMIT = 50


class CatalogRepositoryError(ValueError):
    """Invalid query, duplicate ID or rejected catalog write."""


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return " ".join(value.casefold().split())


class SQLiteAttractionRepository:
    """Insert-only repository; closes its connection as a context manager.

    This is an offline development catalog, not a web-facing multi-tenant API.
    Never expose raw SQL or untrusted database file paths via an HTTP endpoint.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path))
        self._connection.row_factory = sqlite3.Row
        try:
            with self._connection:
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS attractions (
                        attraction_id TEXT PRIMARY KEY NOT NULL,
                        country_code TEXT NOT NULL,
                        city_key TEXT NOT NULL,
                        search_key TEXT NOT NULL,
                        record_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS attractions_city_idx
                      ON attractions (country_code, city_key, attraction_id);
                    """
                )
        except Exception:
            self._connection.close()
            raise

    def __enter__(self) -> "SQLiteAttractionRepository":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def insert(
        self,
        records: tuple[AttractionRecordV1, ...],
        *,
        allow_synthetic_fixtures: bool = False,
    ) -> int:
        """Atomically insert validated entries; never silently overwrite data."""
        if len(records) > MAX_BATCH_RECORDS:
            raise CatalogRepositoryError("Catalog import exceeds bounded batch limit")
        if len({record.attraction_id for record in records}) != len(records):
            raise CatalogRepositoryError("Duplicate attraction IDs in import batch")
        if not allow_synthetic_fixtures and any(
            source.kind == "fixture"
            for record in records for source in record.sources
        ):
            raise CatalogRepositoryError("Synthetic fixture sources are not importable")

        entries = tuple(
            (
                record.attraction_id,
                record.country_code,
                _normalize(record.city),
                _normalize(f"{record.name} {record.city} {record.attraction_id}"),
                record.model_dump_json(),
            )
            for record in records
        )
        try:
            with self._connection:
                self._connection.executemany(
                    """
                    INSERT INTO attractions
                        (attraction_id, country_code, city_key,
                         search_key, record_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    entries,
                )
        except sqlite3.IntegrityError as exc:
            raise CatalogRepositoryError(
                "Attraction ID already exists; import rolled back"
            ) from exc
        return len(entries)

    def get(self, attraction_id: str) -> AttractionRecordV1 | None:
        row = self._connection.execute(
            "SELECT record_json FROM attractions WHERE attraction_id = ?",
            (attraction_id,),
        ).fetchone()
        return (
            AttractionRecordV1.model_validate_json(row["record_json"])
            if row else None
        )

    def search(
        self,
        *,
        country_code: str | None = None,
        city: str | None = None,
        text: str | None = None,
        limit: int = 20,
    ) -> tuple[AttractionRecordV1, ...]:
        """Deterministic name/city/ID substring search; no semantic ranking."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise CatalogRepositoryError("Search limit must be between 1 and 50")
        if country_code is not None and (
            len(country_code) != 2 or not country_code.isascii()
            or not country_code.isalpha() or country_code != country_code.upper()
        ):
            raise CatalogRepositoryError("country_code must be an uppercase ISO alpha-2 code")
        if city is not None and (not city.strip() or len(city) > 120):
            raise CatalogRepositoryError("Invalid city filter")
        if text is not None and (not text.strip() or len(text) > 200):
            raise CatalogRepositoryError("Invalid text query")

        sql = "SELECT record_json FROM attractions WHERE 1=1"
        params: list[str | int] = []
        if country_code is not None:
            sql += " AND country_code = ?"
            params.append(country_code)
        if city is not None:
            sql += " AND city_key = ?"
            params.append(_normalize(city))
        if text is not None:
            sql += " AND instr(search_key, ?) > 0"
            params.append(_normalize(text))
        sql += " ORDER BY attraction_id LIMIT ?"
        params.append(limit)
        rows = self._connection.execute(sql, params).fetchall()
        return tuple(
            AttractionRecordV1.model_validate_json(row["record_json"])
            for row in rows
        )

    def count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS total FROM attractions"
        ).fetchone()
        return int(row["total"])


__all__ = [
    "CatalogRepositoryError", "SQLiteAttractionRepository",
    "MAX_BATCH_RECORDS", "MAX_SEARCH_LIMIT",
]
