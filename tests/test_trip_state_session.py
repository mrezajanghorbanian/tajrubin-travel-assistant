"""Literal user statements in typed session slots, not validated travel facts."""
import json
import pytest
from pydantic import ValidationError

from app.assistant.local_model_session import LocalModelSession, main
from app.providers.text_generation import TextGenerationResponseV1
from app.providers.openai_compatible import OpenAICompatibleProviderError

class Stub:
    def __init__(self):
        self.calls=[]
        self.error=None
        self.payload={'understanding':'درخواست سفر','clarification_question':None,'search':None,'updates':{key:None for key in ('destination','duration','dates','party','budget','preferences')}}
    def generate(self, request):
        self.calls.append(request)
        if self.error:raise self.error
        return TextGenerationResponseV1(text=json.dumps(self.payload,ensure_ascii=False))
    def patch(self, **values):
        self.payload['updates']={key:values.get(key) for key in ('destination','duration','dates','party','budget','preferences')}

def test_partial_update_preserves_other_slots_and_own_source_turn():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    p.patch(destination='شیراز',duration='سه روز',preferences='آرام')
    first=s.send('سه روز شیراز؛ سفر آرام')
    assert first.state_status=='applied'
    old=s.trip_state
    p.patch(dates='۲۰ آبان ۱۴۰۵',party='دو نفر',budget='ده میلیون تومان')
    second=s.send('۲۰ آبان ۱۴۰۵؛ دو نفر؛ ده میلیون تومان')
    p.patch(budget='پانزده میلیون تومان')
    third=s.send('بودجه را پانزده میلیون تومان کن')
    state=third.trip_state
    assert state.destination.value=='شیراز' and state.destination.source_turn==1
    assert state.duration.value=='سه روز' and state.preferences.value=='آرام'
    assert state.party.value=='دو نفر' and state.party.source_turn==2
    assert state.dates.value=='۲۰ آبان ۱۴۰۵'
    assert state.budget.value=='پانزده میلیون تومان' and state.budget.source_turn==3
    assert old.budget is None
    assert json.loads(p.calls[-1].prompt)['trip_state']['budget']['value']=='ده میلیون تومان'
    assert second.trip_state==second.model_copy().trip_state
    with pytest.raises(ValidationError):state.destination.value='تهران'

@pytest.mark.parametrize('bad', [
    {'duration':'پنج روز'},
    {'party':'دو نفر'},
])
def test_nonliteral_patch_rejected_before_tool_with_atomic_state(bad,monkeypatch):
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    p.patch(destination='تهران');s.send('سفر تهران')
    before=(s.trip_state,s.turns)
    p.payload['updates'].update(bad)
    p.payload['search']={'query':'کاخ گلستان','city':'تهران'}
    monkeypatch.setattr('app.assistant.grounded_session.load_local_knowledge_pack',lambda *a:pytest.fail('invalid patch must not search'))
    r=s.send('کاخ گلستان در تهران')
    assert r.state_status=='rejected'
    assert (s.trip_state,s.turns)==before and r.knowledge is None

@pytest.mark.parametrize('updates', [
    {'booked':'yes'}, {'budget':100}, {'party':''}, {'party':'a'*201},
    {'party':'دو نفر','source_turn':7}, None, [],
])
def test_invalid_patch_schema_never_commits(updates):
    p=Stub()
    if isinstance(updates,dict):p.payload['updates'].update(updates)
    else:p.payload['updates']=updates
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('تهران شیراز دو نفر')
    assert r.status=='invalid_model_reply' and s.turns==()
    assert s.trip_state.destination is None

@pytest.mark.parametrize('failure',['timeout','tool_rejected','tool_unavailable'])
def test_failure_cannot_commit_new_fact(failure,monkeypatch):
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    p.patch(destination='شیراز');s.send('سفر شیراز')
    before=(s.trip_state,s.turns)
    p.patch(budget='ده میلیون تومان')
    if failure=='timeout':p.error=OpenAICompatibleProviderError('timeout','private')
    elif failure=='tool_rejected':p.payload['search']={'query':'موزه','city':'تهران'}
    else:
        p.payload['search']={'query':'کاخ گلستان','city':'تهران'}
        def broken(*a):raise OSError('private')
        monkeypatch.setattr('app.assistant.grounded_session.load_local_knowledge_pack',broken)
    r=s.send('ده میلیون تومان؛ کاخ گلستان در تهران')
    assert r.state_status=='not_applied' and (s.trip_state,s.turns)==before
    assert 'private' not in r.model_dump_json()

def test_missing_patch_does_not_erase_state_and_model_summary_is_not_a_source():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    p.patch(destination='شیراز');s.send('سفر شیراز')
    p.patch();p.payload['understanding']='دو نفر در تهران'
    r=s.send('ادامه بده')
    assert r.state_status=='unchanged' and r.trip_state.destination.value=='شیراز'
    assert r.trip_state.party is None
    p.patch(party='دو نفر')
    assert s.send('اطلاعات بیشتر بده').state_status=='rejected'

def test_isolation_and_reset_include_typed_state():
    p=Stub();a=LocalModelSession(provider=p,trip_state=True);b=LocalModelSession(provider=p,trip_state=True)
    p.patch(destination='شیراز');a.send('سفر شیراز')
    p.patch(destination='تهران');b.send('سفر تهران')
    snapshot=a.trip_state
    a.reset()
    assert a.trip_state.destination is None and a.turns==()
    assert snapshot.destination.value=='شیراز' and b.trip_state.destination.value=='تهران'

def test_cli_state_mode_applies_grounded_and_serializes_slots(monkeypatch,capsys):
    p=Stub();p.patch(destination='شیراز')
    class Owned:
        def __enter__(self):return p
        def __exit__(self,*a):pass
    monkeypatch.setattr('app.assistant.local_model_session.build_local_text_generation_provider',lambda c:Owned())
    lines=iter(['سفر شیراز','/exit']);monkeypatch.setattr('builtins.input',lambda:next(lines))
    assert main(['--trip-state','--format','json'])==0
    r=json.loads(capsys.readouterr().out)
    assert r['trip_state']['destination']=={'value':'شیراز','source_turn':1}
    assert r['tool_status']=='not_requested'

def test_state_mode_can_commit_knowledge_and_statements_together():
    p=Stub();p.patch(destination='تهران')
    p.payload['search']={'query':'کاخ گلستان','city':'تهران'}
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('سفر تهران؛ درباره کاخ گلستان بگو')
    assert r.state_status=='applied' and r.knowledge.status=='provisional'
    assert r.knowledge.evidence[0].document_id=='ir.tehran.golestan-palace'
    assert r.trip_state.destination.value=='تهران'
    schema=json.loads(p.calls[0].response_schema_json)
    assert set(schema['required'])=={'understanding','clarification_question','search','updates'}
    assert schema['additionalProperties'] is False
    assert 'source_turn' not in p.calls[0].response_schema_json
    assert len(p.calls)==1

def test_model_cannot_replay_old_statement_as_new_evidence():
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    p.patch(budget='ده میلیون تومان');s.send('بودجه ده میلیون تومان')
    before=(s.trip_state,s.turns)
    assert s.send('ادامه بده').state_status=='rejected'
    assert (s.trip_state,s.turns)==before

def test_context_limit_does_not_modify_state_or_call_model():
    from app.assistant.local_model_session import SessionLimitError
    p=Stub();s=LocalModelSession(provider=p,trip_state=True)
    p.patch(destination='شیراز');s.send('سفر شیراز')
    before=(s.trip_state,s.turns)
    with pytest.raises(SessionLimitError):s.send('الف'*666)
    assert len(p.calls)==1 and (s.trip_state,s.turns)==before

def test_omitted_updates_key_is_invalid_and_cannot_erase_state():
    p=Stub();del p.payload['updates']
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('سفر شیراز')
    assert r.status=='invalid_model_reply' and r.state_status=='not_applied'
    assert s.trip_state.destination is None

def test_cli_rejected_patch_has_nonzero_exit_and_farsi_slot_labels(monkeypatch,capsys):
    p=Stub();p.patch(destination='تهران')
    class Owned:
        def __enter__(self):return p
        def __exit__(self,*a):pass
    monkeypatch.setattr('app.assistant.local_model_session.build_local_text_generation_provider',lambda c:Owned())
    lines=iter(['سفر شیراز','/exit']);monkeypatch.setattr('builtins.input',lambda:next(lines))
    assert main(['--trip-state','--format','json'])==1
    assert json.loads(capsys.readouterr().out)['state_status']=='rejected'
    lines=iter(['سفر تهران','/exit'])
    assert main(['--trip-state'])==0
    out=capsys.readouterr().out
    assert 'مقصد: تهران' in out and 'destination:' not in out

def test_duplicate_json_state_keys_are_rejected_not_last_value_wins():
    p=Stub()
    p.generate=lambda request:TextGenerationResponseV1(text='{"understanding":"x","clarification_question":null,"search":null,"updates":{"destination":"تهران","destination":"شیراز","duration":null,"dates":null,"party":null,"budget":null,"preferences":null}}')
    s=LocalModelSession(provider=p,trip_state=True)
    assert s.send('تهران شیراز').status=='invalid_model_reply'
    assert s.turns==() and s.trip_state.destination is None

def test_every_slot_key_is_required_in_model_patch():
    p=Stub();del p.payload['updates']['budget']
    s=LocalModelSession(provider=p,trip_state=True)
    assert s.send('سفر شیراز').status=='invalid_model_reply'
    assert s.turns==()

def test_mixed_literal_and_invented_update_cannot_partially_commit():
    p=Stub();p.patch(destination='تهران',party='دو نفر')
    s=LocalModelSession(provider=p,trip_state=True)
    r=s.send('سفر تهران')
    assert r.state_status=='rejected'
    assert s.trip_state.destination is None and s.trip_state.party is None
