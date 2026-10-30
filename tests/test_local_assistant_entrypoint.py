"""One offline entry point for grounded questions and planning readiness."""
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.assistant.grounded_qa import TravelQuestionV1


@pytest.mark.parametrize(('text', 'city', 'source'), [
    ('کاخ گلستان', 'تهران', 'https://whc.unesco.org/en/list/1422/'),
    ('Masjed-e Jame', 'Isfahan', 'https://whc.unesco.org/en/list/1397/'),
    ('شهر تاریخی یزد', 'یزد', 'https://whc.unesco.org/en/list/1544/'),
])
def test_question_routes_to_bilingual_knowledge_with_sources(text, city, source):
    from app.assistant.entrypoint import handle_local_request

    result = handle_local_request(TravelQuestionV1(question=text, city=city, country_code='IR'))
    assert result.kind == 'knowledge_answer'
    assert result.planning is None
    assert result.knowledge.status == 'provisional'
    assert result.knowledge.evidence[0].external_urls == (source,)
    assert result.live_verified is False
    assert result.needs_verification is True


@pytest.mark.parametrize(('text', 'filters'), [
    ('astronaut orbital station', {}),
    ('Golestan Palace ticket prices', {'city': 'Tehran'}),
    ('کاخ گلستان', {'city': 'Shiraz'}),
    ('کاخ گلستان', {'country_code': 'GB'}),
])
def test_question_keeps_abstention_and_filters(text, filters):
    from app.assistant.entrypoint import handle_local_request

    result = handle_local_request(TravelQuestionV1(question=text, **filters))
    assert result.kind == 'knowledge_answer'
    assert result.knowledge.status == 'insufficient_evidence'
    assert result.knowledge.evidence == ()
    assert result.planning is None


@pytest.mark.parametrize(('text', 'blocker'), [
    ('Plan a 3 day trip', 'destinations'),
    ('برای تهران برنامه سفر میخواهم', 'duration_days'),
    ('Plan a 3 day trip to Tehran from 2026-11-03 to 2026-11-04', 'duration_conflict'),
])
def test_planning_routes_to_specific_clarification(text, blocker):
    from app.assistant.entrypoint import handle_local_request

    result = handle_local_request(TravelQuestionV1(question=text))
    assert result.kind == 'planning_readiness'
    assert result.knowledge is None
    assert result.planning.status == 'needs_clarification'
    assert blocker in result.planning.blockers
    assert result.planning.clarification_question
    assert result.planning.draft_specification is None
    assert result.live_verified is False


@pytest.mark.parametrize('text', ['Plan a 3 day trip to Tehran', 'برای ۳ روز تهران برنامه سفر میخواهم'])
def test_resolved_request_only_returns_unverified_draft_inputs(text, tmp_path):
    from app.assistant.entrypoint import handle_local_request

    result = handle_local_request(TravelQuestionV1(question=text), knowledge_root=tmp_path / 'missing')
    assert result.planning.status == 'ready_for_draft'
    spec = result.planning.draft_specification
    assert spec.destinations == ('Tehran',)
    assert spec.duration_days == 3
    assert spec.dates is None
    assert spec.logistics_verified is False
    assert result.knowledge is None
    assert result.needs_verification is True


@pytest.mark.parametrize('filters', [{'city': 'Tehran'}, {'country_code': 'IR'}])
def test_planning_does_not_silently_discard_knowledge_filters(filters):
    from app.assistant.entrypoint import handle_local_request

    with pytest.raises(ValueError, match='filters apply only to knowledge questions'):
        handle_local_request(TravelQuestionV1(question='Plan a 3 day trip to Shiraz', **filters))


@pytest.mark.parametrize(('text', 'kind', 'status'), [
    ('کاخ گلستان', 'knowledge_answer', 'provisional'),
    ('ساعت بازدید کاخ گلستان', 'knowledge_answer', 'insufficient_evidence'),
    ('Plan a 3 day trip', 'planning_readiness', 'needs_clarification'),
    ('برای ۳ روز تهران برنامه سفر میخواهم', 'planning_readiness', 'ready_for_draft'),
])
def test_unified_module_runs_end_to_end(text, kind, status):
    result = subprocess.run(
        [sys.executable, '-X', 'utf8', '-m', 'app.assistant', text, '--format', 'json'],
        check=True, capture_output=True, encoding='utf-8',
    )
    payload = json.loads(result.stdout)
    assert payload['kind'] == kind
    branch = 'knowledge' if kind == 'knowledge_answer' else 'planning'
    assert payload[branch]['status'] == status
    assert payload['live_verified'] is False
    assert payload['needs_verification'] is True


def test_text_question_shows_source_url(capsys):
    from app.assistant.entrypoint import main

    assert main(['کاخ گلستان']) == 0
    assert 'https://whc.unesco.org/en/list/1422/' in capsys.readouterr().out


def test_text_planning_asks_for_missing_information_in_persian(capsys):
    from app.assistant.entrypoint import main

    assert main(['برای تهران برنامه سفر میخواهم']) == 0
    assert 'روز' in capsys.readouterr().out


@pytest.mark.parametrize('text', ['x', 'a' * 2001])
def test_unified_cli_rejects_invalid_request(text, capsys):
    from app.assistant.entrypoint import main

    assert main([text, '--format', 'json']) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'Local assistant input error' in captured.err


def test_missing_knowledge_pack_only_blocks_question_route(tmp_path, capsys):
    from app.assistant.entrypoint import main

    assert main(['کاخ گلستان', '--knowledge-root', str(tmp_path / 'missing')]) == 2
    assert 'Local assistant input error' in capsys.readouterr().err


def test_response_contract_rejects_mixed_or_wrong_branch_payloads():
    from app.assistant.entrypoint import LocalAssistantResponseV1, handle_local_request
    from app.assistant.planning_readiness import analyze_planning_request

    knowledge = handle_local_request(TravelQuestionV1(question='کاخ گلستان')).knowledge
    planning = handle_local_request(TravelQuestionV1(question='Plan a 3 day trip')).planning
    with pytest.raises(ValidationError):
        LocalAssistantResponseV1(kind='knowledge_answer', knowledge=knowledge, planning=planning)
    with pytest.raises(ValidationError):
        LocalAssistantResponseV1(kind='planning_readiness', knowledge=knowledge)
    with pytest.raises(ValidationError):
        LocalAssistantResponseV1(kind='planning_readiness', planning=analyze_planning_request('کاخ گلستان'))


def test_unified_cli_preserves_result_limit(capsys):
    from app.assistant.entrypoint import main

    assert main(['Tehran', '--max-results', '1', '--format', 'json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result['knowledge']['evidence']) == 1


@pytest.mark.parametrize('options', [['--max-results', '0'], ['--country', 'INVALID']])
def test_unified_cli_rejects_invalid_knowledge_options(options, capsys):
    from app.assistant.entrypoint import main

    assert main(['کاخ گلستان', '--format', 'json', *options]) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'Local assistant input error' in captured.err


def test_entrypoint_requires_no_signing_or_provider_runtime():
    script = (
        "import sys; sys.modules['cryptography'] = None; sys.modules['httpx'] = None; "
        "from app.assistant.entrypoint import handle_local_request; "
        "from app.assistant.grounded_qa import TravelQuestionV1; "
        "r = handle_local_request(TravelQuestionV1(question='Plan a 3 day trip to Tehran')); "
        "print(r.kind); "
        "print(handle_local_request(TravelQuestionV1(question='Golestan Palace')).kind)"
    )
    result = subprocess.run([sys.executable, '-c', script], check=True, capture_output=True, encoding='utf-8')
    assert result.stdout.splitlines() == ['planning_readiness', 'knowledge_answer']
