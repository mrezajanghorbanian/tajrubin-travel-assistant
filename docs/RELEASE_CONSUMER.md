# Current Editorial Approval Gate for Signed Release Consumption

`app/knowledge/release_consumer.py` links the complete offline prototype pipeline:

**approved editorial records → publisher-issued channel-bound Ed25519 release → verification → current editorial recheck → persisted anti-rollback acceptance**.

A valid signature alone is **not** enough to expose travel records. Each consumer request verifies the complete signature and channel, compares the signed records with the current editorially approved snapshot, checks for expired sources and revoked records, and only then updates the local accepted-sequence counter. A second editorial check after acceptance reduces the window for concurrent changes.

## Run tests

```bash
python -m pytest tests/test_release_consumer.py tests/test_release_pipeline_integration.py -q
```

## Boundaries and limitations

- Requires live access to the trusted **editorial database**. It is not an offline source of revocation truth. Loss of editorial connectivity fails closed.
- Changing the approved set makes an old snapshot unusable, even if the old items are still individually approved. The current approach deliberately prefers safety over continued availability.
- A revocation or change after the last check can still happen. This is a **best-effort dual-read barrier**, not cross-database ACID, serializable publication, a distributed lock, or cryptographically authenticated revocation.
- Consumer anti-rollback state can advance before a post-acceptance recheck fails. No records are returned in that case, but the release may need republishing under a new sequence.
- The SQLite stores, trust registry, clocks and role verifier are not secured by this module; production deployments require hardened databases and identity services.
- Editorially reviewed records are **not guaranteed factually accurate**. Live hours, availability, licensing and routing evidence remain separate prerequisites.

All tests use synthetic records, synthetic editorial metadata and ephemeral keys only. No real attraction claims have been published.
