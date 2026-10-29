"""A strict per-case synthetic retrieval gate and its CLI exit contract."""
import json
import subprocess
import sys

import pytest

from tools import evaluate_retrieval as evaluation


@pytest.mark.parametrize(('relevant', 'returned', 'k', 'passed'), [
    (['a', 'b'], ['a'], 1, True),
    (['a', 'b'], ['a'], 3, False),
    ([], ['noise'], 3, False),
    (['a'], ['a', 'a'], 3, False),
    (['a', 'b'], ['a', 'b'], 1, False),
    ([], [], 3, True),
])
def test_gate_distinguishes_cutoff_coverage_and_false_positive_failures(relevant, returned, k, passed):
    gate = evaluation.assess([
        {'id': 'example', 'relevant_ids': relevant, 'retrieved_ids': returned},
    ], k=k)
    assert gate['passed'] is passed
    assert bool(gate['failures']) is not passed


def test_empty_case_set_cannot_pass_gate():
    gate = evaluation.assess([], k=3)
    assert gate['passed'] is False
    assert gate['errors'] == ['empty_case_set']


def test_gate_reports_specific_missing_and_unexpected_results():
    gate = evaluation.assess([
        {'id': 'broken', 'relevant_ids': ['a', 'b'], 'retrieved_ids': ['a', 'noise']},
        {'id': 'safe-negative', 'relevant_ids': [], 'retrieved_ids': []},
    ], k=3)
    assert gate['passed'] is False
    assert gate['failures'] == [{
        'case_id': 'broken', 'unexpected_ids': ['noise'],
        'missing_relevant_count': 1, 'duplicate_ids': [], 'over_limit': False,
    }]


@pytest.mark.parametrize(('check', 'exit_code'), [(False, 0), (True, 1)])
def test_cli_emits_failure_report_and_only_fails_when_check_enabled(tmp_path, monkeypatch, capsys, check, exit_code):
    fixture = {
        'version': 1, 'synthetic': True,
        'documents': [{
            'document_id': 'museum', 'country_code': 'IR', 'country_name': 'Iran',
            'city': 'Tehran', 'category': 'attraction', 'title': 'Museum',
            'summary': 'Synthetic museum guide', 'content': 'Synthetic example only',
        }],
        'cases': [{
            'id': 'missed-garden', 'language': 'en',
            'query': {'text': 'garden', 'city': 'Tehran'}, 'relevant_ids': ['museum'],
        }],
    }
    path = tmp_path / 'controlled-failure.json'
    path.write_text(json.dumps(fixture), encoding='utf-8')
    monkeypatch.setitem(evaluation.FIXTURES, 'bilingual', path)
    args = ['--suite', 'bilingual'] + (['--check'] if check else [])
    assert evaluation.main(args) == exit_code
    report = json.loads(capsys.readouterr().out)
    assert report['bilingual']['gate']['passed'] is False
    assert report['bilingual']['gate']['failures'][0]['case_id'] == 'missed-garden'
    assert report['bilingual']['gate']['failures'][0]['missing_relevant_count'] == 1


@pytest.mark.parametrize('suite', ['bilingual', 'persian-plurals'])
def test_real_cli_checks_candidate_without_gating_weaker_default(suite):
    result = subprocess.run(
        [sys.executable, '-m', 'tools.evaluate_retrieval', '--suite', suite, '--check'],
        check=True, capture_output=True, encoding='utf-8',
    )
    report = json.loads(result.stdout)
    assert report['bilingual']['gate']['passed'] is True
    assert report['bilingual']['gate']['failures'] == []
    assert report['default']['gate']['passed'] is False


def test_module_exits_nonzero_after_a_real_alias_regression():
    # Remove aliases only inside this child process; exercise the real
    # retriever, evaluator and module exit path against unchanged gold labels.
    script = (
        "import runpy, sys; from app.retrieval import in_memory; "
        "in_memory.CURATED_TRAVEL_TERMS = {}; "
        "sys.argv = ['tools.evaluate_retrieval', '--check']; "
        "runpy.run_module('tools.evaluate_retrieval', run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, '-c', script], capture_output=True, encoding='utf-8',
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['bilingual']['gate']['passed'] is False
    assert report['bilingual']['gate']['failures']
