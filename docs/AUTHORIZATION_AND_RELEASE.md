# Editorial Authorization and Content-Addressed Releases (Prototype)

## Current implemented boundary

`app/knowledge/editorial_access.py` requires an externally verified identity and permits only explicit roles. There is **no built-in identity provider, password, real JWT implementation or public HTTP endpoint**.

| Role | Permitted API methods |
| --- | --- |
| contributor | Submit candidate attraction records |
| reviewer | Review, revoke, inspect pending and audit records |
| auditor | Inspect pending and audit history |
| publisher | Read editorially approved records |

No access is granted by default. Submitters cannot review their own entries, and users with inactive identities cannot perform privileged actions. Actors and dates are taken from the verified principal and injected trusted clock, **not from untrusted client-supplied fields**. In this prototype the verifier must independently validate issuer, signature, audience, expiration, revocation and roles.

**Trust warning:** A caller that instantiates `SQLiteEditorialReviewQueue` directly can bypass this access boundary. Future production deployment must encapsulate or restrict direct database access and expose only the authorized service.

## Snapshot format

`app/knowledge/release_snapshot.py` builds a deterministic, content-addressed record bundle, sorted by ID, with SHA-256 digest and count. It exports only editorially approved, non-revoked records valid on the release date.

This is a **content-integrity checksum, not cryptographic authenticity, certification of travel facts or a trusted signature**. A publisher with database access can replace content and recompute its hash. A revoked record also remains present in historical snapshots; consumers must check a trusted current release manifest/revocation policy before using past exports.

To avoid accidental truncation, the first version deliberately fails if the approved result reaches the configured maximum. It supports only small offline releases (under 50 records). Pagination, revision semantics and signed manifests are not yet implemented.

## Tests

```bash
python -m pytest tests/test_editorial_access_release.py -q
python -m pytest -q
```

The unit-test verifier contains intentionally fake token labels and **must never be used in production**. All attraction records are synthetic fixtures.

## Required before public deployment

1. Real identity provider with secure key rotation, issuer/audience validation, expiry and revocation.
2. Tenant-scoped RBAC and server-side audit timestamps/authorization on every call.
3. Privileged database isolation, access monitoring, concurrency controls and audit retention.
4. Signed release manifests with independently managed signing keys and explicit revocation of old releases.
5. Validated source licensing, independent fact checks, and trusted route/opening-hours providers.
6. Pagination, migration/version control, and production-scale quality evaluation.
