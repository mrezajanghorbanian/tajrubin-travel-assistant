# Persistent Release State v1

This phase adds a trusted-process issuance boundary and durable anti-rollback acceptance for signed catalog releases.

**Issuance:** `EditorialAccessService.create_release_snapshot(credential)` requires an externally verified principal with `publisher` role; it draws the release date from its trusted clock rather than an arbitrary client parameter. Signing the resulting snapshot must be done by the external key custodian via `sign_catalog_release`; no keys are committed.

**Consumption:** `SQLiteReleaseState.accept(...)` verifies the full Ed25519 envelope using trusted public keys and a trusted clock, and atomically stores the highest accepted sequence per release channel in SQLite. Replaying an older sequence is rejected. Retrying an identical signed release is idempotent; conflicting content at the same sequence is refused. Invalid signatures and expired releases cannot advance the stored counter.

This **does not authenticate a deployment or provide secure hardware-backed storage**. Anyone with write access to the SQLite file may roll back, replace or delete it. An external service needs protected persistence, backup monotonicity, secure clock, authorization to invoke the signer, atomic cross-service issuance, and replay protection across replicas.

The complete issuance chain is not yet exposed as a network endpoint. No authentication provider, KMS/HSM or real tourism-source verification is connected.

```bash
python -m pytest tests/test_release_state.py tests/test_signed_release.py -q
```

All signing keys used by tests are ephemeral in-memory test keys. The project must not ship a default issuer, secret, or private key.
