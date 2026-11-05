# Publisher-authorized SQLite Release Issuer (Prototype)

`SQLiteCatalogReleaseIssuer` binds editorial approval, trusted publisher authorization and Ed25519 v2 signing to a transactionally recorded per-channel sequence. It is designed for **trusted offline processes**, not a public issuance API.

## Steps

1. Validate channel, signing key ID, idempotency request ID and lifetime limits.
2. Acquire an SQLite `BEGIN IMMEDIATE` writer transaction so same-ledger issuers cannot reserve the same sequence simultaneously.
3. Revalidate publisher permissions through `EditorialAccessService.create_release_snapshot` using an externally verified principal and trusted date.
4. Refuse an empty or potentially truncated approved catalog.
5. For an idempotent retry, return the previously signed envelope only if key, current approved snapshot and release policy still match.
6. Otherwise increment the channel's committed sequence, sign the full v2 payload with an **external signer**, verify with a configured trusted public key, and save the signed envelope atomically.
7. Signing errors, authorization errors and invalid signatures roll back without committing a version.

## Reproducible tests

```bash
python -m pytest tests/test_release_issuer.py -q
python -m pytest tests -q
```

Tests use ephemeral test-only key pairs and synthetic attraction claims. No private key is checked into Git.

## Production caveats

- The editorial review store may be a **different database** from the issuer ledger; therefore approval reads and publication writes are *not* one cross-database transaction. Concurrent revocation and approval changes need a coordinated release publication lock or immutable approved snapshots.
- SQLite transactions protect this one database but do not guarantee remote KMS signing exactly once. A key provider might sign an envelope before a subsequent database transaction fails; the signed bytes are not considered published until durably committed.
- A trusted identity provider, KMS/HSM, protected database filesystem, audit trail, recovery plan, secret rotation and rate limits are not yet integrated.
- Issuance does not independently verify attraction metadata, opening hours, legal licensing or travel feasibility.
- Per-channel issuance version is separate from the consumer-side `SQLiteReleaseState` anti-rollback counter.
- All APIs remain non-networked prototypes. The caller must only serve the committed issued envelope and avoid publishing raw snapshots.

## Next technical priorities

Authenticated publisher service, coordinated immutable editorial revision snapshots, secure KMS signing with revision-stability checks, credential-revocation policies, source provenance validation and a production release/deployment pipeline.
