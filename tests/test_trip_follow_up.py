"""Required-detail policy is application-owned, never a substitute model reply."""
import json
import pytest
from app.assistant.local_model_session import LocalModelSession, main
from app.providers.text_generation import TextGenerationResponseV1
from app.providers.openai_compatible import OpenAICompatibleProviderError

class Stub:
    def __init__(self):
        self.calls=[];self.error=None
        self.payload={'understanding':'درخواست سفر','clarification_question':None,'search':None,'updates':{k:None for k in ('destination','duration','dates','party','budget','preferences')}}
    def patch(self,**values):
        self.payload['updates']={k:values.get(k) for k in self.payload['updates']}
    def generate(self,request):
        self.calls.append(request)
        if self.error:raise self.error
        return TextGenerationResponseV1(text=json.dumps(self.payload,ensure_ascii=False))

def test_model_null_question_gets_explicit_application_date_question():
    p=Stub();p.patch(destination='شیراز',duration='سه روز',preferences='آرام')
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('شیراز سه روز آرام')
    assert r.intake.clarification_question is None
    assert r.follow_up.source=='application_policy' and r.follow_up.requested_field=='dates'
    assert r.follow_up.status=='needs_details' and 'dates' in r.follow_up.missing_fields
    assert 'تاریخ' in r.follow_up.question and s.pending_question==r.follow_up.question
    assert len(p.calls)==1
    assert s.turns[-1].intake.clarification_question is None
    assert s.turns[-1].application_question==r.follow_up.question

def test_answered_date_is_not_asked_again_and_prior_facts_survive():
    p=Stub();p.patch(destination='شیراز',duration='سه روز')
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('شیراز سه روز')
    p.patch(dates='۲۰ آبان ۱۴۰۵',party='دو نفر')
    r2=s.send('۲۰ آبان ۱۴۰۵؛ دو نفر')
    assert r2.follow_up.status=='needs_validation'
    assert r2.follow_up.missing_fields==() and r2.follow_up.question is None
    assert s.pending_question is None
    assert r2.trip_state.destination==r.trip_state.destination
    history=json.loads(p.calls[-1].prompt)
    assert history['previous_turns'][0]['application_question']==r.follow_up.question
    assert history['previous_turns'][0]['assistant']['clarification_question'] is None

@pytest.mark.parametrize(('values','message','field'),[
    ({},'سفر می‌خوام','destination'),
    ({'destination':'شیراز'},'سفر شیراز','dates'),
    ({'destination':'شیراز','dates':'۲۰ آبان'},'شیراز ۲۰ آبان','duration'),
    ({'destination':'شیراز','dates':'۲۰ آبان','duration':'سه روز'},'شیراز ۲۰ آبان سه روز','party'),
])
def test_required_detail_priority(values,message,field):
    p=Stub();p.patch(**values)
    r=LocalModelSession(provider=p,trip_state=True).send(message)
    assert r.follow_up.requested_field==field and r.follow_up.source=='application_policy'

def test_model_question_is_preserved_with_source_and_missing_fields_visible():
    p=Stub();p.patch(destination='شیراز');p.payload['clarification_question']='سه روز یا پنج روز؟'
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('شیراز سه روز یا پنج روز')
    assert r.follow_up.source=='model' and r.follow_up.question==r.intake.clarification_question
    assert r.follow_up.requested_field is None
    assert 'dates' in r.follow_up.missing_fields and s.pending_question==r.follow_up.question

@pytest.mark.parametrize('failure',['model','patch','tool'])
def test_failure_cannot_advance_question_or_state(failure):
    p=Stub();p.patch(destination='شیراز')
    s=LocalModelSession(provider=p,trip_state=True)
    s.send('شیراز')
    before=(s.pending_question,s.trip_state,s.turns)
    p.patch(dates='۲۰ آبان')
    if failure=='model':p.error=OpenAICompatibleProviderError('timeout','private')
    if failure=='patch':p.patch(dates='۲۱ آبان')
    if failure=='tool':p.payload['search']={'query':'کاخ گلستان','city':'تهران'}
    r=s.send('۲۰ آبان')
    assert r.follow_up is None and (s.pending_question,s.trip_state,s.turns)==before
    assert 'private' not in r.model_dump_json()

def test_knowledge_gap_can_still_request_required_details():
    p=Stub();p.patch(destination='شیراز',duration='سه روز')
    p.payload['search']={'query':'شیراز','city':'شیراز'}
    r=LocalModelSession(provider=p,trip_state=True).send('شیراز سه روز؛ اطلاعات شیراز')
    assert r.knowledge.status=='insufficient_evidence'
    assert r.follow_up.requested_field=='dates'
    assert r.intake.clarification_question is None

def test_isolation_and_reset_clear_effective_question():
    p=Stub();p.patch(destination='شیراز')
    a=LocalModelSession(provider=p,trip_state=True);b=LocalModelSession(provider=p,trip_state=True)
    a.send('شیراز');assert a.pending_question is not None and b.pending_question is None
    a.reset();assert a.pending_question is None and a.turns==()

def test_cli_prints_one_effective_question_without_mutating_model_text(monkeypatch,capsys):
    p=Stub();p.patch(destination='شیراز',duration='سه روز')
    class Owned:
        def __enter__(self):return p
        def __exit__(self,*a):pass
    monkeypatch.setattr('app.assistant.local_model_session.build_local_text_generation_provider',lambda c:Owned())
    lines=iter(['شیراز سه روز','/exit']);monkeypatch.setattr('builtins.input',lambda:next(lines))
    assert main(['--trip-state'])==0
    out=capsys.readouterr().out
    assert out.count('تاریخ شروع سفر')==1

@pytest.mark.parametrize('change',[
    {'status':'needs_validation'}, {'source':None}, {'requested_field':'party'},
    {'question':None}, {'missing_fields':('dates','dates')},
])
def test_inconsistent_question_metadata_is_rejected(change):
    from pydantic import ValidationError
    from app.assistant.trip_state import TripFollowUpV1
    payload={'status':'needs_details','missing_fields':('dates',),'question':'تاریخ؟','source':'application_policy','requested_field':'dates'}
    payload.update(change)
    with pytest.raises(ValidationError):TripFollowUpV1(**payload)

def test_all_required_literal_fields_never_means_ready_and_optional_fields_do_not_block():
    p=Stub();p.patch(destination='شیراز',dates='۲۰ آبان',duration='سه روز',party='دو نفر')
    r=LocalModelSession(provider=p,trip_state=True).send('شیراز ۲۰ آبان سه روز دو نفر')
    assert r.follow_up.status=='needs_validation' and r.follow_up.question is None
    assert r.trip_state.budget is None and r.trip_state.preferences is None
    assert r.live_verified is False and r.needs_verification is True

@pytest.mark.parametrize('change',[
    {'clarification_question':' '},
    {'follow_up':{'source':'application_policy','question':'fabricated'}},
])
def test_invalid_model_output_never_gets_a_policy_question(change):
    p=Stub();p.patch(destination='شیراز');p.payload.update(change)
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('شیراز')
    assert r.status=='invalid_model_reply' and r.follow_up is None
    assert s.pending_question is None and s.turns==() and s.trip_state.destination is None
