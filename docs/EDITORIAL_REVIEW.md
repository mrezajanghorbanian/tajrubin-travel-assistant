# Editorial Review v1 — Staging and Publication Gate

This module introduces an **offline SQLite editorial queue**. It deliberately separates submitted candidate attraction records from the approved publication view.

## State transitions

`pending` → `approved` or `rejected`; `approved` → `revoked`.

- Submitter and reviewer must differ (case-insensitive comparison).
- Reviewer must provide a non-empty reason.
- Every decision is recorded in an append-only *application event table*, with record checksum, actor, date and reason.
- Duplicate IDs and all fixture-source records are rejected at submission.
- Approval checks the full record schema and all sources' stated observation and expiry dates.
- `approved(as_of=...)` only returns records approved by that day, not revoked, with non-fixture date-valid source claims.
- Approved records are still **not independently fact-checked**. The source type, observed date and URLs are claims, not cryptographic proof.
- Revocation removes records from the approved output. Previous events remain visible in `audit()`.
- Revisions require a **new attraction ID** in this prototype. No production update or conflict resolution is implemented.

## Security boundary

**Do not expose this local class as a public editorial API.** Caller-supplied actor IDs are not authenticated. A public service needs authenticated identities, RBAC, audit-log protections, transactional isolation against concurrent editors, retention policy, monitoring and permission tests. Because the SQLite event log is writable by local database administrators, it is **not tamper-proof**.

Use the approved view as a candidate input to a separate validated release process. Publication must not use pending or raw catalog search results. The scheduler's time-specific source freshness checks continue to apply to approved candidates.

## Tests

```bash
python -m pytest tests/test_editorial_review.py -q
```

All test attraction data and URLs are synthetic examples, not verified attraction facts.

## Next work

- Add an authenticated reviewer service and role-based access.
- Verify sources independently with publication rights/licensing.
- Implement approval revisions, staged diffs and optimistic locking.
- Build the editorial UI, audit export and source monitoring.
- Integrate approved records into the public search/indexing layer only after release gates.
