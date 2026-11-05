"""Authorization and publication snapshot safety tests; synthetic records only."""
from datetime import date, time
import hashlib
import pytest
from pydantic import ValidationError

from app.knowledge.attraction_catalog import (
    AttractionRecordV1, CatalogSourceV1, GeoPointV1, DatedOpeningV1,
)
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.editorial_access import (
    AuthorizationDenied, EditorialAccessService, VerifiedPrincipalV1,
)
from app.knowledge.release_snapshot import (
    CatalogReleaseSnapshotV1, ReleaseSnapshotError,
    create_editorial_release_snapshot,
)

TODAY = date(2026, 10, 26)


def attraction(name="test.gallery"):
    s = CatalogSourceV1(
        source_id="test.source", title="Synthetic editorial source",
        kind="editorial", url="https://example.org/synthetic",
        observed_at=date(2026, 10, 1), valid_through=date(2026, 12, 1),
    )
    return AttractionRecordV1(
        attraction_id=name, knowledge_document_id="test.knowledge",
        name="Synthetic Gallery", country_code="IR", city="Tehran",
        location=GeoPointV1(latitude=35, longitude=51, source_id=s.source_id),
        visit_duration_minutes=60, duration_source_id=s.source_id,
        opening_windows=(DatedOpeningV1(
            on_date=date(2026, 11, 3), opens_at=time(9),
            closes_at=time(17), source_id=s.source_id,
        ),), sources=(s,),
    )


class FakeVerifier:
    """Identity fixture, not a production JWT / authentication provider."""
    def verify(self, token):
        roles = {
            "submitter": ("alice", frozenset({"contributor"})),
            "reviewer": ("bob", frozenset({"reviewer"})),
            "publisher": ("carol", frozenset({"publisher"})),
            "auditor": ("dave", frozenset({"auditor"})),
            "inactive": ("eve", frozenset({"reviewer"})),
        }
        if token not in roles:
            raise ValueError("invalid credential")
        subject, user_roles = roles[token]
        return VerifiedPrincipalV1(
            subject=subject, roles=user_roles, active=token != "inactive"
        )


def service(q):
    return EditorialAccessService(q, FakeVerifier(), current_date=lambda: TODAY)


def test_unauthenticated_and_invalid_credentials_denied(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        api = service(q)
        for credential in ("", "bad-token", None):
            with pytest.raises(AuthorizationDenied):
                api.submit(credential, (attraction(),))


def test_inactive_principal_denied(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        with pytest.raises(AuthorizationDenied):
            service(q).pending("inactive")


def test_least_privilege_roles(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        api = service(q)
        api.submit("submitter", (attraction(),))
        with pytest.raises(AuthorizationDenied):
            api.review("submitter", "test.gallery", decision="approve", reason="ok")
        with pytest.raises(AuthorizationDenied):
            api.submit("publisher", (attraction("test.two"),))
        with pytest.raises(AuthorizationDenied):
            api.pending("publisher")
        with pytest.raises(AuthorizationDenied):
            api.approved("reviewer")
        assert len(api.pending("auditor")) == 1
        assert api.audit("auditor", "test.gallery")[0].action == "submit"


def test_identity_comes_from_verifier_and_cannot_self_review(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        api = service(q)
        api.submit("submitter", (attraction(),))
        api.review("reviewer", "test.gallery", decision="approve", reason="ok")
        assert api.approved("publisher") == (attraction(),)


def test_snapshot_cannot_include_pending_records(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        service(q).submit("submitter", (attraction(),))
        s = create_editorial_release_snapshot(q, created_on=TODAY, maximum_records=10)
        assert s.record_count == 0
        assert s.authenticity_verified is False


def test_snapshot_content_address_and_tamper_detection(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        api = service(q)
        api.submit("submitter", (attraction(),))
        api.review("reviewer", "test.gallery", decision="approve", reason="ok")
        snapshot = create_editorial_release_snapshot(q, created_on=TODAY, maximum_records=10)
        assert snapshot.record_count == 1
        assert len(snapshot.content_sha256) == 64
        with pytest.raises(ValidationError, match="hash"):
            CatalogReleaseSnapshotV1.model_validate(
                snapshot.model_dump() | {"content_sha256": "0" * 64}
            )


def test_revoked_record_absent_from_next_snapshot(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        api = service(q)
        api.submit("submitter", (attraction(),))
        api.review("reviewer", "test.gallery", decision="approve", reason="ok")
        before = create_editorial_release_snapshot(q, created_on=TODAY, maximum_records=10)
        api.revoke("reviewer", "test.gallery", reason="incorrect metadata")
        after = create_editorial_release_snapshot(q, created_on=TODAY, maximum_records=10)
        assert before.record_count == 1
        assert after.record_count == 0
        assert before.content_sha256 != after.content_sha256


def test_snapshot_rejects_possible_truncation(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path / "q.db") as q:
        api = service(q)
        api.submit("submitter", (attraction(),))
        api.review("reviewer", "test.gallery", decision="approve", reason="ok")
        with pytest.raises(ReleaseSnapshotError, match="truncated"):
            create_editorial_release_snapshot(q, created_on=TODAY, maximum_records=1)
