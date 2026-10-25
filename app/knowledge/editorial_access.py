"""Explicit role authorization boundary for the *trusted-process* editorial API.

The verifier is intentionally an injected dependency: there is no anonymous
fallback, shared development password, local magic token, or default identity.
Only an external, independently configured identity provider can authenticate
a bearer credential. This module alone is NOT a production login system.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.attraction_catalog import AttractionRecordV1
from app.knowledge.editorial_review import (
    Decision, ReviewEventV1, SQLiteEditorialReviewQueue,
)

Role = Literal["contributor", "reviewer", "auditor", "publisher"]


class AuthorizationDenied(PermissionError):
    """No verified identity or insufficient privilege; fail closed."""


class VerifiedPrincipalV1(BaseModel):
    """Claims must be returned by an external authenticated verifier ONLY."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    subject: str = Field(
        min_length=1, max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._@-]*$",
    )
    roles: frozenset[Role] = Field(min_length=1)
    active: bool = True


class IdentityVerifier(Protocol):
    """Provider must verify issuer, audience, signature, expiry and revocation."""

    def verify(self, credential: str) -> VerifiedPrincipalV1:
        ...


_PERMISSIONS: dict[str, frozenset[Role]] = {
    "submit": frozenset({"contributor"}),
    "review": frozenset({"reviewer"}),
    "revoke": frozenset({"reviewer"}),
    "pending": frozenset({"reviewer", "auditor"}),
    "audit": frozenset({"reviewer", "auditor"}),
    "approved": frozenset({"publisher"}),
}


class EditorialAccessService:
    """Narrow API surface; no method accepts caller-supplied actor identifiers."""

    def __init__(
        self,
        queue: SQLiteEditorialReviewQueue,
        verifier: IdentityVerifier,
        *,
        current_date: Callable[[], date],
    ) -> None:
        if queue is None or verifier is None or not callable(current_date):
            raise ValueError("Editorial service requires queue, verifier and trusted clock")
        self._queue = queue
        self._verifier = verifier
        self._current_date = current_date

    def _today(self) -> date:
        today = self._current_date()
        if type(today) is not date:
            raise AuthorizationDenied("Trusted clock is unavailable")
        return today

    def _require(self, credential: str, action: str) -> VerifiedPrincipalV1:
        if not isinstance(credential, str) or not 1 <= len(credential) <= 4096:
            raise AuthorizationDenied("Valid authentication is required")
        try:
            principal = self._verifier.verify(credential)
        except Exception as exc:
            raise AuthorizationDenied("Valid authentication is required") from exc
        if not isinstance(principal, VerifiedPrincipalV1):
            raise AuthorizationDenied("Verifier did not supply a verified identity")
        if not principal.active or principal.roles.isdisjoint(_PERMISSIONS[action]):
            raise AuthorizationDenied("Operation not permitted")
        return principal

    def submit(
        self,
        credential: str,
        records: tuple[AttractionRecordV1, ...],
    ) -> int:
        principal = self._require(credential, "submit")
        return self._queue.submit(
            records, submitted_by=principal.subject, submitted_on=self._today()
        )

    def review(
        self,
        credential: str,
        attraction_id: str,
        *,
        decision: Decision,
        reason: str,
    ) -> str:
        principal = self._require(credential, "review")
        return self._queue.decide(
            attraction_id, reviewed_by=principal.subject,
            reviewed_on=self._today(), decision=decision, reason=reason,
        )

    def revoke(
        self,
        credential: str,
        attraction_id: str,
        *,
        reason: str,
    ) -> None:
        principal = self._require(credential, "revoke")
        self._queue.revoke(
            attraction_id, revoked_by=principal.subject,
            revoked_on=self._today(), reason=reason,
        )

    def pending(
        self,
        credential: str,
        *,
        limit: int = 20,
    ) -> tuple[AttractionRecordV1, ...]:
        self._require(credential, "pending")
        return self._queue.pending(limit=limit)

    def audit(
        self,
        credential: str,
        attraction_id: str,
    ) -> tuple[ReviewEventV1, ...]:
        self._require(credential, "audit")
        return self._queue.audit(attraction_id)

    def approved(
        self,
        credential: str,
        *,
        limit: int = 20,
        country_code: str | None = None,
        city: str | None = None,
    ) -> tuple[AttractionRecordV1, ...]:
        self._require(credential, "approved")
        return self._queue.approved(
            as_of=self._today(), limit=limit,
            country_code=country_code, city=city,
        )


__all__ = [
    "AuthorizationDenied", "EditorialAccessService",
    "IdentityVerifier", "VerifiedPrincipalV1", "Role",
]
