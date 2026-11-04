"""Same-session confirmation and existing signed-preview integration; synthetic data."""
import json
from datetime import date
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.assistant.local_model_session import LocalModelSession, main
from app.providers.text_generation import TextGenerationResponseV1
from app.providers.openai_compatible import OpenAICompatibleProviderError
from app.assistant.trip_preview import preview_trip_readiness
from app.assistant.catalog_to_scheduler import VisitSelectionV1
from app.knowledge.editorial_review import SQLiteEditorialReviewQueue
from app.knowledge.release_issuer import SQLiteCatalogReleaseIssuer
from app.knowledge.release_state import SQLiteReleaseState
from tests.test_release_pipeline_integration import TODAY, DESTINATION_DATE, setup_approved, issuance

class Stub:
    def __init__(self):
        self.calls=[];self.error=None
        self.payload={'understanding':'درخواست سفر','clarification_question':None,'search':None,'updates':{k:None for k in ('destination','duration','dates','party','budget','preferences')}}
    def patch(self,**values):self.payload['updates']={k:values.get(k) for k in self.payload['updates']}
    def generate(self,request):
        self.calls.append(request)
        if self.error:raise self.error
        return TextGenerationResponseV1(text=json.dumps(self.payload,ensure_ascii=False))

def ready(p,s,**updates):
    values={'destination':'تهران','duration':'یک روز','dates':'2026-11-03','party':'دو نفر',**updates}
    p.patch(**values)
    s.send('برای سفر؛ '+ '؛ '.join(values.values()))

def test_default_confirmation_returns_missing_evidence_not_fabricated_trip():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    ready(p,s)
    assert s.planning_preview is None
    r=s.confirm_trip()
    assert r.status=='blocked' and r.preview.status=='needs_activity_selection'
    assert r.preview.schedule is None and r.live_verified is False
    assert r.readiness.draft_specification.party_size==2
    assert len(p.calls)==1 and len(s.turns)==1

@pytest.mark.parametrize(('updates','field'),[
    ({'dates':'۲۰ آبان ۱۴۰۵'},'dates'),
    ({'dates':'2026-02-30'},'dates'),
    ({'duration':'3 or 5 days'},'duration'),
    ({'duration':'2 days or 32 days'},'duration'),
    ({'party':'2 people or 31 people'},'party'),
    ({'destination':'ناشهر'},'destination'),
    ({'destination':'تهران و شیراز'},'destination'),
    ({'budget':'۱۵ میلیون تومان'},'budget'),
    ({'budget':'هرچقدر لازم شد'},'budget'),
    ({'preferences':'سفر آرام با ویلچر'},'preferences'),
])
def test_unresolved_constraints_never_reach_scheduling(updates,field):
    p=Stub()
    s=LocalModelSession(provider=p,trip_state=True,preview_runner=lambda r:pytest.fail('must not schedule'))
    ready(p,s,**updates)
    result=s.confirm_trip()
    assert result.status=='needs_validation' and result.preview is None
    assert field in {b.field for b in result.blockers}
    assert result.statements.model_dump()[field]['value']==updates[field]

def test_dates_duration_conflict_remains_blocked():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    ready(p,s,duration='3 days',dates='2026-11-03 to 2026-11-04')
    r=s.confirm_trip()
    assert r.status=='needs_validation' and 'duration_conflict' in r.readiness.blockers

def test_current_corrected_values_used_and_new_turn_invalidates_old_preview():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    ready(p,s,dates='2026-11-03',duration='دو روز')
    old=s.confirm_trip()
    p.patch(duration='سه روز');s.send('مدت را سه روز کن')
    assert s.planning_preview is None
    new=s.confirm_trip()
    assert old.readiness.draft_specification.duration_days==2
    assert new.readiness.draft_specification.duration_days==3
    assert new.statements.duration.source_turn==2
    assert 'دو روز' not in new.readiness.intent.base.request

def test_failed_update_preserves_confirmed_preview_and_reset_isolates_state():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    ready(p,s);old=s.confirm_trip()
    p.error=OpenAICompatibleProviderError('timeout','private')
    s.send('سه روز کن')
    assert s.planning_preview==old
    other=LocalModelSession(provider=p,trip_state=True)
    assert other.confirm_trip().status=='needs_details'
    s.reset();assert s.planning_preview is None and s.trip_state.destination is None

def test_signed_fixture_flows_through_same_session_to_real_scheduler(tmp_path):
    key=Ed25519PrivateKey.generate()
    with SQLiteEditorialReviewQueue(tmp_path/'review.db') as queue:
        api=setup_approved(queue)
        with SQLiteCatalogReleaseIssuer(tmp_path/'issuer.db') as issuer:
            release=issuance(issuer,api,key)
        with SQLiteReleaseState(tmp_path/'accepted.db') as state:
            def runner(readiness):
                return preview_trip_readiness(readiness,
                    selections=(VisitSelectionV1(attraction_id='synthetic.gallery',day_index=1,on_date=DESTINATION_DATE),),
                    release=release,trusted_keys={'ephemeral-key':key.public_key()},
                    current_date=lambda:TODAY,editorial=queue,state=state)
            p=Stub();s=LocalModelSession(provider=p,trip_state=True,preview_runner=runner)
            ready(p,s)
            r=s.confirm_trip()
            assert r.status=='provisional'
            assert r.preview.schedule.days[0].visits[0].activity_id=='synthetic.gallery'
            assert r.preview.source_document_ids==('synthetic.knowledge',)
            api.revoke('reviewer','synthetic.gallery',reason='Withdrawn')
            revoked=s.confirm_trip()
            assert revoked.status=='blocked' and revoked.preview.status=='evidence_rejected'
            assert revoked.preview.schedule is None

def test_cli_confirm_is_explicit_application_action(monkeypatch,capsys):
    p=Stub();p.patch(destination='تهران',duration='یک روز',dates='2026-11-03',party='دو نفر')
    class Owned:
        def __enter__(self):return p
        def __exit__(self,*a):pass
    monkeypatch.setattr('app.assistant.local_model_session.build_local_text_generation_provider',lambda c:Owned())
    lines=iter(['تهران یک روز 2026-11-03 دو نفر','/confirm','/exit'])
    monkeypatch.setattr('builtins.input',lambda:next(lines))
    assert main(['--trip-state','--format','json'])==0
    out=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert out[-1]['kind']=='planning_preview' and out[-1]['status']=='blocked'
    assert len(p.calls)==1

@pytest.mark.parametrize(('updates','field'),[
    ({'party':'31 or 2 people'},'party'),
    ({'party':'2 to 4 people'},'party'),
    ({'duration':'not 3 days'},'duration'),
    ({'destination':'not Tehran'},'destination'),
    ({'dates':'not 2026-11-03'},'dates'),
])
def test_partial_regex_match_cannot_confirm_an_entire_ambiguous_statement(updates,field):
    p=Stub();s=LocalModelSession(provider=p,trip_state=True,preview_runner=lambda r:pytest.fail('must not schedule'))
    ready(p,s,**updates)
    r=s.confirm_trip()
    assert r.status=='needs_validation' and field in {b.field for b in r.blockers}

def test_tool_errors_are_sanitized_and_mismatched_preview_not_reused():
    p=Stub()
    def broken(readiness):raise OSError('private path')
    s=LocalModelSession(provider=p,trip_state=True,preview_runner=broken)
    ready(p,s)
    failed=s.confirm_trip()
    assert failed.status=='unavailable' and 'private' not in failed.model_dump_json()
    assert s.trip_state.destination.value=='تهران'

def test_confirmation_is_unavailable_outside_trip_state_mode():
    with pytest.raises(ValueError):LocalModelSession(provider=Stub()).confirm_trip()

def test_preview_for_old_readiness_or_missing_schedule_is_not_accepted():
    from app.assistant.planning_readiness import analyze_planning_request
    from app.assistant.trip_preview import TripPreviewV1
    old=analyze_planning_request('Plan a 2 day trip to Tehran on 2026-11-03')
    p=Stub();s=LocalModelSession(provider=p,trip_state=True,
        preview_runner=lambda current:TripPreviewV1(status='needs_activity_selection',readiness=old,feedback='old'))
    ready(p,s)
    assert s.confirm_trip().status=='unavailable'
    s=LocalModelSession(provider=p,trip_state=True,
        preview_runner=lambda current:TripPreviewV1(status='provisional',readiness=current,feedback='bad'))
    ready(p,s)
    assert s.confirm_trip().status=='unavailable'

def test_planning_question_is_attributed_and_correction_invalidates_it():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    ready(p,s,dates='۲۰ آبان ۱۴۰۵')
    validation=s.confirm_trip()
    assert s.pending_question==validation.question
    p.patch(dates='2026-11-20');s.send('تاریخ میلادی 2026-11-20')
    assert json.loads(p.calls[-1].prompt)['planning_question']==validation.question
    assert s.planning_preview is None
    assert s.confirm_trip().preview.status=='needs_activity_selection'
    assert s.pending_question is None
