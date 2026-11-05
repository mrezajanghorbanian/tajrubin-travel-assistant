# Editorially Approved Planning Gateway

The offline function `build_reviewed_itinerary` is the first safe junction between the review queue and the date-aware deterministic scheduler.

## Flow

1. Read the explicit travel specification and selected activity IDs and dates.
2. Verify that every selected date corresponds to its declared day index.
3. Fetch exactly those activity IDs through `SQLiteEditorialReviewQueue.approved_by_ids`, not the raw attraction repository.
4. Require every activity to be approved at the supplied review date, without revocation, duplicate IDs, synthetic sources or invalid source metadata.
5. Recheck **each visit day's** evidence freshness via `build_visit_candidates`.
6. Require source-provided directed travel times and dated opening windows to build a provisional schedule.
7. Reject the entire request on missing or conflicting facts.

This module never authorizes a booking, verifies a URL, calls a routing service or authenticates a reviewer. A caller could lie about the `review_as_of` date; production code must supply it from a trusted clock and enforce authenticated roles.

## Usage and validation

```bash
python -m pytest tests/test_reviewed_itinerary.py tests/test_editorial_review.py -q
```

Test records and coordinates are **synthetic** and never constitute factual claims about any real Iranian attraction.

## Security and design limits

- The editorial queue is still a local trusted-process library, **not** an authenticated endpoint.
- The database event log is not tamper-evident against privileged SQLite modification; record SHA-256 only detects payload modification without digest updates.
- `approved_by_ids` fails closed at the gateway whenever a requested ID is omitted from the approved result.
- A production service needs a trusted review timestamp, authenticated reviewer identity, locked-down publication role, independent provenance verification, URL/SSRF controls, and historical publication snapshots.
- Travel-time records remain caller-supplied and unverified; the schedule is always provisional.

## Next action

Build an authenticated reviewer service and formal release snapshot with signed audit metadata before launching a public interface.
