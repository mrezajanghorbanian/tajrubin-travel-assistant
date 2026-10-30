# Ed25519 Signed Catalog Releases v1

The signed envelope protects a complete canonical catalog snapshot together with the release sequence, signing-key identifier, release expiry and protocol domain. Ed25519 signatures are produced by an **externally supplied signer**. This code **never generates, stores, exports, prints or commits production private keys**.

## Install

```bash
python -m pip install -e '.[signing]'
python -m pytest tests/test_signed_release.py -q
```

An external key custodian may provide an Ed25519 signing object implementing `sign(message: bytes) -> bytes`. Consumers must configure **trusted Ed25519 public keys** keyed by `key_id`. Unknown or removed keys are rejected; there is no anonymous fallback.

## Verification requirements

- A snapshot is validated against its nested content checksum and signed as a canonical JSON payload.
- Verification covers all release records, expiry date, sequence, key ID and protocol domain.
- The verifier requires a trusted current date and configured trusted key. Future-dated and expired releases are rejected.
- Consumers must keep a **trusted persistent highest accepted sequence** to prevent rollback/replay. The verifier accepts `minimum_sequence` but does not store this state.
- A signature does not make travel source claims true, guarantee current opening hours, or imply booking availability.
- Production deployments must verify provenance and publisher authorization **before** signing, protect signing keys outside the repository, configure revocation/rotation, and distribute trusted keys by an authenticated channel.

## Security boundaries

These utilities are offline cryptographic primitives, **not** a fully integrated production release service. No JWKS fetcher, remote key-management system, issuance endpoint, authenticated publisher or historical revocation feed is implemented. The code does not publish data or contact outside services.

Never include development signing keys or plaintext long-term secrets in the public repository, test fixtures or GitHub Actions logs. Unit tests generate ephemeral key pairs in memory.

## What remains before public launch

1. Integrate trusted identity provider and publisher role with server-side enforcement.
2. Use external KMS/HSM or well-protected signing service; verify publisher permissions and version monotonicity at issuance.
3. Pin and rotate public keys with authenticated distribution.
4. Store accepted release counters durably and implement revocation semantics.
5. Populate the attraction catalog with independently verified, properly licensed real data.
