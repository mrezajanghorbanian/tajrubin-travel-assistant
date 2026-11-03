import json
import pytest
from pydantic import ValidationError
from app.providers.openai_compatible import OpenAICompatibleProviderError
from app.providers.text_generation import TextGenerationResponseV1
from app.assistant.local_model_session import LocalModelSession, SessionLimitError, main

class Stub:
    def __init__(self):
        self.calls = []
        self.error = None
        self.text = json.dumps({'understanding': 'سفر سه روزه شیراز', 'clarification_question': 'چه تاریخی؟'})
    def generate(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return TextGenerationResponseV1(text=self.text)

def test_followup_preserves_literal_user_facts_and_pending_question():
    provider = Stub()
    session = LocalModelSession(provider=provider)
    session.send('سه روز شیراز با بودجه کم')
    first = session.turns
    session.send('از ۲۰ آبان؛ دو نفر هستیم')
    history = json.loads(provider.calls[-1].prompt)
    assert history['previous_turns'][0]['user'] == 'سه روز شیراز با بودجه کم'
    assert history['previous_turns'][0]['assistant']['clarification_question'] == 'چه تاریخی؟'
    assert history['current_user'] == 'از ۲۰ آبان؛ دو نفر هستیم'
    assert len(first) == 1 and len(session.turns) == 2
    assert session.pending_question == 'چه تاریخی؟'

@pytest.mark.parametrize('failure', ['invalid', 'timeout'])
def test_failed_turn_is_atomic_and_retry_has_no_failed_message(failure):
    provider = Stub()
    session = LocalModelSession(provider=provider)
    session.send('سه روز شیراز')
    before = session.turns
    if failure == 'timeout':
        provider.error = OpenAICompatibleProviderError('timeout', 'private diagnostic')
    else:
        provider.text = '{bad'
    result = session.send('دو نفر هستیم')
    assert result.status != 'model_reply'
    assert session.turns == before
    provider.error = None
    provider.text = json.dumps({'understanding':'شیراز', 'clarification_question':None})
    session.send('یک نفر هستم')
    assert 'دو نفر هستیم' not in provider.calls[-1].prompt
    assert session.pending_question is None

def test_sessions_are_isolated_and_reset_clears_only_owner():
    p = Stub()
    a, b = LocalModelSession(provider=p), LocalModelSession(provider=p)
    a.send('سفر شیراز')
    b.send('سفر تهران')
    assert 'شیراز' not in p.calls[-1].prompt
    snapshot = a.turns
    a.reset()
    assert a.turns == () and a.pending_question is None
    assert len(b.turns) == 1 and len(snapshot) == 1
    with pytest.raises(ValidationError):
        snapshot[0].message = 'changed'

@pytest.mark.parametrize('message', ['', 'x', 'a'*2001])
def test_invalid_input_never_calls_provider(message):
    p = Stub()
    s = LocalModelSession(provider=p)
    with pytest.raises(ValueError):
        s.send(message)
    assert p.calls == [] and s.turns == ()

def test_limits_do_not_truncate_or_call_model():
    p = Stub()
    s = LocalModelSession(provider=p)
    for _ in range(4):
        s.send('سفر شیراز')
    with pytest.raises(SessionLimitError):
        s.send('ادامه سفر')
    assert len(p.calls) == 4 and len(s.turns) == 4
    s.reset()
    with pytest.raises(SessionLimitError):
        s.send('a'*2000)
    assert s.turns == () and len(p.calls) == 4

def test_cli_multiple_inputs_and_reset(monkeypatch, capsys):
    p = Stub()
    monkeypatch.setattr('app.assistant.local_model_session.build_local_text_generation_provider', lambda config: Context(p))
    lines = iter(['سفر شیراز','دو نفر هستیم','/reset','سفر تهران','/exit'])
    monkeypatch.setattr('builtins.input', lambda: next(lines))
    assert main(['--format','json']) == 0
    replies = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert len(replies) == 3
    assert 'شیراز' in p.calls[1].prompt and 'شیراز' not in p.calls[2].prompt

class Context:
    def __init__(self, p): self.p = p
    def __enter__(self): return self.p
    def __exit__(self, *args): pass

def test_large_prior_reply_stops_before_discarding_facts():
    p = Stub()
    p.text = json.dumps({'understanding':'الف'*650, 'clarification_question':None}, ensure_ascii=False)
    s = LocalModelSession(provider=p)
    s.send('سه روز شیراز')
    before = s.turns
    with pytest.raises(SessionLimitError):
        s.send('دو نفر هستیم')
    assert s.turns == before and len(p.calls) == 1

def test_cli_eof_closes_provider_and_error_exit_is_nonzero(monkeypatch, capsys):
    p = Stub()
    p.error = OpenAICompatibleProviderError('timeout','private diagnostic')
    closed = []
    class Owned(Context):
        def __exit__(self, *args): closed.append(True)
    monkeypatch.setattr('app.assistant.local_model_session.build_local_text_generation_provider', lambda config: Owned(p))
    lines = iter(['سفر شیراز'])
    def read():
        try: return next(lines)
        except StopIteration: raise EOFError
    monkeypatch.setattr('builtins.input',read)
    assert main(['--format','json']) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['error_code'] == 'timeout' and closed == [True]
    assert 'private diagnostic' not in json.dumps(result)
