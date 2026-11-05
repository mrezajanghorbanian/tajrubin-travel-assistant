# SQLite Attraction Repository — Initial Local Implementation

The initial catalog layer now supports **bounded, offline, validated** JSON ingestion and durable search. This is not a verified travel dataset, a remote crawler, a production API, or semantic/vector retrieval.

## Components

- `app/knowledge/attraction_catalog.py`: strict Pydantic schema with source IDs, dated opening windows, location, visit duration, and accessibility metadata.
- `app/knowledge/catalog_import.py`: local UTF-8 JSON parser with version validation, duplicate-key/ID detection, strict schema validation and a 2MB input-size cap.
- `app/knowledge/catalog_repository.py`: SQLite-backed insert-only catalog with transactional batch writes and parameterized lookups and substring filtering.
- `app/assistant/catalog_to_scheduler.py`: rejects stale and fixture-only claims before conversion to the itinerary scheduler by default.

## Import format

```json
{
  "catalog_version": "1.0",
  "records": []
}
```

The record structure is defined by `AttractionRecordV1`; fields may not be silently added or ignored. No real attractions have been bulk ingested.

## Example: deliberate local import

```python
from app.knowledge.catalog_import import load_catalog_json
from app.knowledge.catalog_repository import SQLiteAttractionRepository

records = load_catalog_json("catalog.json")
with SQLiteAttractionRepository("local_attractions.sqlite3") as repository:
    repository.insert(records)  # Fixture sources rejected by default.
    result = repository.search(country_code="IR", city="Tehran", limit=20)
    for entry in result:
        print(entry.attraction_id, entry.name)
```

## Security and quality boundaries

- SQLite queries use bound parameters, not SQL string concatenation of user values.
- Duplicate IDs cause atomic transaction rollback. Importing does not silently overwrite records.
- Non-HTTPS and missing provenance URLs are rejected by the source schema; URLs are **not fetched or authenticated** by the importer.
- Source kind `official` / `editorial` is declared metadata; the database does not independently prove authenticity. An attacker can provide a fabricated URL or misleading date. These records remain **unverified** until editorial approval.
- Synthetic fixture records are rejected by default at import and scheduling boundaries.
- Source valid-through metadata can block the scheduler, but the repository's raw `search` deliberately does not certify freshness. Query results must pass the adapter's freshness gate.
- The database path must be trusted configuration, never directly supplied by anonymous web users.
- All sample test data are artificial and not real-world claims.
- This is a local development repository; there is not yet a migration framework, multi-user permissions, moderation workflow, source verification pipeline, or cloud backup.

## Validation

```bash
python -m pytest tests/test_catalog_repository.py tests/test_attraction_catalog.py -q
python tools/security_gate.py
```

Release status and results must be checked in GitHub Actions on the actual commit. Do not assume a passing local test implies all CI checks passed.

## Future work

- Establish a human-reviewed ingestion queue that separates candidate records from approved production records.
- Integrate authoritative or independently reviewed attraction sources with retention/licensing controls.
- Design approved/unverified state transitions and audit history before any public publishing.
- Implement map/routing travel-time evidence and itinerary availability refresh rules.
- Introduce schema migrations and an appropriate persistence backend when concurrent publishing becomes necessary.
