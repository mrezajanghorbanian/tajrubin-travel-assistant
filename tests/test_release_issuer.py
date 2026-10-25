"""Transactional issuer tests with synthetic editorial records and ephemeral keys."""
from datetime import date, time
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.knowledge.attraction_catalog import AttractionRecordV1, CatalogSourceV1, GeoPointV1, DatedOpeningV1
from app.knowledge.editorial_access import EditorialAccessService, VerifiedPrincipalV1, AuthorizationDenied
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.release_issuer import SQLiteCatalogReleaseIssuer, ReleaseIssuanceError
from app.knowledge.release_protocol_v2 import verify_release_v2

TODAY=date(2026,10,26)


class Verifier:
    def verify(self, credential):
        if credential == "publisher":
            return VerifiedPrincipalV1(subject="carol",roles=frozenset({"publisher"}))
        if credential == "reviewer":
            return VerifiedPrincipalV1(subject="bob",roles=frozenset({"reviewer"}))
        raise ValueError("bad credentials")


def record():
    s=CatalogSourceV1(
        source_id="test.source",title="Synthetic source",kind="editorial",
        url="https://example.org/test",observed_at=date(2026,10,1),
        valid_through=date(2026,12,1),
    )
    return AttractionRecordV1(
        attraction_id="synthetic.gallery",knowledge_document_id="synthetic.doc",
        name="Synthetic Gallery",country_code="IR",city="Tehran",
        location=GeoPointV1(latitude=35,longitude=51,source_id=s.source_id),
        visit_duration_minutes=60,duration_source_id=s.source_id,
        opening_windows=(DatedOpeningV1(
            on_date=date(2026,11,3),opens_at=time(9),closes_at=time(17),source_id=s.source_id
        ),),sources=(s,),
    )


def prepared(tmp_path):
    queue=SQLiteEditorialReviewQueue(tmp_path/"editorial.db")
    queue.submit((record(),),submitted_by="alice",submitted_on=TODAY)
    queue.decide("synthetic.gallery",reviewed_by="bob",reviewed_on=TODAY,
                 decision="approve",reason="Fixture metadata review")
    api=EditorialAccessService(queue,Verifier(),current_date=lambda:TODAY)
    return queue,api


def issue(issuer,api,key,request_id="req-1",credential="publisher",signer=None):
    return issuer.issue(
        api,credential,channel="iran",key_id="test",request_id=request_id,
        signer=signer or key,trusted_keys={"test":key.public_key()},
        maximum_records=10,
    )


def test_initial_issue_is_signed_and_persisted(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        release=issue(issuer,api,key)
        assert release.sequence==1
        assert issuer.last_issued_sequence("iran")==1
        verified=verify_release_v2(
            release,expected_channel="iran",trusted_keys={"test":key.public_key()},
            current_date=lambda:TODAY,
        )
        assert verified.record_count==1


def test_retries_idempotent_and_persistent(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    db=tmp_path/"issuance.db"
    with queue,SQLiteCatalogReleaseIssuer(db) as issuer:
        first=issue(issuer,api,key)
        second=issue(issuer,api,key)
        assert first==second
    with SQLiteEditorialReviewQueue(tmp_path/"editorial.db") as reopened_queue, SQLiteCatalogReleaseIssuer(db) as issuer:
        reopened_api=EditorialAccessService(reopened_queue,Verifier(),current_date=lambda:TODAY)
        third=issue(issuer,reopened_api,key,request_id="req-2")
        assert third.sequence==2


def test_unauthorized_issuance_does_not_advance(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        with pytest.raises(AuthorizationDenied):
            issue(issuer,api,key,credential="reviewer")
        assert issuer.last_issued_sequence("iran") is None


def test_broken_signer_does_not_advance(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    class Broken:
        def sign(self, payload):
            raise RuntimeError("KMS unavailable")
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        with pytest.raises(RuntimeError,match="KMS"):
            issue(issuer,api,key,signer=Broken())
        assert issuer.last_issued_sequence("iran") is None
        assert issue(issuer,api,key).sequence==1


def test_different_key_or_policy_same_request_rejected(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        issue(issuer,api,key)
        with pytest.raises(ReleaseIssuanceError,match="conflicts"):
            issuer.issue(
                api,"publisher",channel="iran",key_id="test",request_id="req-1",
                signer=key,trusted_keys={"test":key.public_key()},
                lifetime_days=2,maximum_records=10,
            )
        assert issuer.last_issued_sequence("iran")==1


def test_no_publish_empty_catalog(tmp_path):
    q=SQLiteEditorialReviewQueue(tmp_path/"editorial.db")
    api=EditorialAccessService(q,Verifier(),current_date=lambda:TODAY)
    key=Ed25519PrivateKey.generate()
    with q,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        with pytest.raises(ReleaseIssuanceError,match="Empty"):
            issue(issuer,api,key)
        assert issuer.last_issued_sequence("iran") is None


def test_revoked_catalog_blocks_retry(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        issue(issuer,api,key)
        queue.revoke("synthetic.gallery",revoked_by="bob",revoked_on=TODAY,reason="withdrawn")
        with pytest.raises(ReleaseIssuanceError,match="Empty"):
            issue(issuer,api,key)
        assert issuer.last_issued_sequence("iran")==1


def test_invalid_channel_and_id_fail_closed(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        with pytest.raises(ReleaseIssuanceError,match="channel"):
            issuer.issue(api,"publisher",channel="iran/../bad",key_id="test",request_id="req-1",signer=key,trusted_keys={"test":key.public_key()},maximum_records=10)
        with pytest.raises(ReleaseIssuanceError,match="request"):
            issue(issuer,api,key,request_id="")
        assert issuer.last_issued_sequence("iran") is None


def test_key_mismatch_signer_is_not_committed(tmp_path):
    queue,api=prepared(tmp_path)
    key=Ed25519PrivateKey.generate()
    wrong=Ed25519PrivateKey.generate()
    with queue,SQLiteCatalogReleaseIssuer(tmp_path/"issuance.db") as issuer:
        with pytest.raises(Exception,match="signature"):
            issue(issuer,api,key,signer=wrong)
        assert issuer.last_issued_sequence("iran") is None
