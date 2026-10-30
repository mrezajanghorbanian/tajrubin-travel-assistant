"""Offline, versioned catalog JSON loader with strict validation and size caps."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.knowledge.attraction_catalog import AttractionRecordV1
from app.knowledge.catalog_repository import MAX_BATCH_RECORDS

MAX_CATALOG_FILE_BYTES = 2_000_000


class CatalogImportError(ValueError):
    """Invalid, ambiguous or unsupported attraction catalog input."""


def _unique_object_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise CatalogImportError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise CatalogImportError(f"Non-finite JSON number is prohibited: {value}")


def load_catalog_json(path: str | Path) -> tuple[AttractionRecordV1, ...]:
    """Load local UTF-8 JSON only; never fetch links found in source records."""
    source_path = Path(path)
    if source_path.is_symlink() or not source_path.is_file():
        raise CatalogImportError("Input must be a regular, non-symlink file")
    if source_path.stat().st_size > MAX_CATALOG_FILE_BYTES:
        raise CatalogImportError("Catalog input exceeds byte limit")

    try:
        raw = source_path.read_bytes()
        if len(raw) > MAX_CATALOG_FILE_BYTES:
            raise CatalogImportError("Catalog input exceeds byte limit")
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogImportError("Invalid UTF-8 catalog JSON") from exc

    if not isinstance(parsed, dict) or set(parsed) != {"catalog_version", "records"}:
        raise CatalogImportError("Expected catalog_version and records only")
    if parsed["catalog_version"] != "1.0":
        raise CatalogImportError("Unsupported catalog version")
    records = parsed["records"]
    if not isinstance(records, list) or len(records) > MAX_BATCH_RECORDS:
        raise CatalogImportError("Catalog records must be a bounded JSON array")

    try:
        validated = tuple(AttractionRecordV1.model_validate(item) for item in records)
    except ValidationError as exc:
        raise CatalogImportError("Catalog record violates attraction schema") from exc
    if len({record.attraction_id for record in validated}) != len(validated):
        raise CatalogImportError("Duplicate attraction IDs in catalog")
    return validated


__all__ = [
    "CatalogImportError", "MAX_CATALOG_FILE_BYTES", "load_catalog_json",
]
