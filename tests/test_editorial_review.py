"""Editorial queue regression tests; entirely synthetic attraction records."""
from datetime import date, time
import pytest
from app.knowledge.attraction_catalog import AttractionRecordV1, CatalogSourceV1, GeoPointV1, DatedOpeningV1
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue, EditorialWorkflowError

TODAY=date(2026,10,26)
def record(name="sample.one",kind="editorial",until=date(2026,12,31)):
    source=CatalogSourceV1(source_id="sample.source",title="Synthetic test source",kind=kind,
        url=None if kind=="fixture" else "https://example.org/test",
        observed_at=date(2026,10,1),valid_through=until)
    return AttractionRecordV1(attraction_id=name,knowledge_document_id="sample.doc",
        name="Synthetic museum",country_code="IR",city="Tehran",
        location=GeoPointV1(latitude=35,longitude=51,source_id="sample.source"),
        visit_duration_minutes=60,duration_source_id="sample.source",
        opening_windows=(DatedOpeningV1(on_date=date(2026,11,3),opens_at=time(9),closes_at=time(17),source_id="sample.source"),),
        sources=(source,))

def test_unreviewed_not_public(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        assert q.approved(as_of=TODAY)==()
        assert len(q.pending())==1

def test_independent_approval_and_audit(tmp_path):
    db=tmp_path/"a.db"
    with SQLiteEditorialReviewQueue(db) as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        assert q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="approve",reason="Claims reviewed")=="approved"
        assert q.approved(as_of=TODAY)==(record(),)
        assert [x.action for x in q.audit("sample.one")]==["submit","approve"]
        assert len({x.record_sha256 for x in q.audit("sample.one")})==1
    with SQLiteEditorialReviewQueue(db) as q:
        assert len(q.approved(as_of=TODAY))==1

def test_self_review_prohibited(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="Alice",submitted_on=TODAY)
        with pytest.raises(EditorialWorkflowError,match="Self"):
            q.decide("sample.one",reviewed_by="alice",reviewed_on=TODAY,decision="approve",reason="ok")
        assert q.approved(as_of=TODAY)==()

def test_rejected_never_visible(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="reject",reason="Insufficient evidence")
        assert q.approved(as_of=TODAY)==()
        assert [x.action for x in q.audit("sample.one")]==["submit","reject"]

def test_expired_source_cannot_be_approved(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(until=date(2026,10,20)),),submitted_by="alice",submitted_on=TODAY)
        with pytest.raises(EditorialWorkflowError,match="expired"):
            q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="approve",reason="ok")
        assert q.pending()[0].attraction_id=="sample.one"

def test_expiration_hides_previously_approved(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(until=date(2026,10,27)),),submitted_by="alice",submitted_on=TODAY)
        q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="approve",reason="ok")
        assert len(q.approved(as_of=TODAY))==1
        assert q.approved(as_of=date(2026,10,28))==()

def test_revoke_removes_from_approved(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="approve",reason="ok")
        q.revoke("sample.one",revoked_by="bob",revoked_on=TODAY,reason="updated information")
        assert q.approved(as_of=TODAY)==()
        assert [e.action for e in q.audit("sample.one")]==["submit","approve","revoke"]

def test_fixture_cannot_enter_queue(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        with pytest.raises(EditorialWorkflowError,match="fixtures"):
            q.submit((record(kind="fixture"),),submitted_by="alice",submitted_on=TODAY)

def test_atomic_duplicate_submission(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        with pytest.raises(EditorialWorkflowError,match="rolled back"):
            q.submit((record("sample.two"),record()),submitted_by="alice",submitted_on=TODAY)
        assert len(q.pending())==1
        assert q.audit("sample.two")==()

def test_duplicate_review_prohibited(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="approve",reason="ok")
        with pytest.raises(EditorialWorkflowError,match="Only pending"):
            q.decide("sample.one",reviewed_by="carol",reviewed_on=TODAY,decision="approve",reason="ok")

def test_future_approval_not_visible_early(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        q.decide("sample.one",reviewed_by="bob",reviewed_on=date(2026,11,1),decision="approve",reason="ok")
        assert q.approved(as_of=TODAY)==()

def test_review_requires_reason(tmp_path):
    with SQLiteEditorialReviewQueue(tmp_path/"a.db") as q:
        q.submit((record(),),submitted_by="alice",submitted_on=TODAY)
        with pytest.raises(EditorialWorkflowError,match="review reason"):
            q.decide("sample.one",reviewed_by="bob",reviewed_on=TODAY,decision="approve",reason=" ")
