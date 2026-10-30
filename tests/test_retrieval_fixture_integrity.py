"""Reject structurally invalid gold data before a retrieval score is reported."""
from copy import deepcopy
import json

import pytest

from tools import evaluate_retrieval as evaluation


def valid_fixture():
    return {
        'version': 1, 'synthetic': True,
        'documents': [{
            'document_id': 'museum', 'country_code': 'IR', 'country_name': 'Iran',
            'city': 'Tehran', 'category': 'attraction', 'title': 'Museum',
            'summary': 'Synthetic museum guide', 'content': 'Synthetic example only',
        }],
        'cases': [
            {'id': 'positive', 'language': 'en', 'query': {'text': 'museum'}, 'relevant_ids': ['museum']},
            {'id': 'negative', 'language': 'fa', 'query': {'text': 'پزشک'}, 'relevant_ids': []},
        ],
    }


def write_fixture(tmp_path, monkeypatch, data):
    path = tmp_path / 'fixture.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setitem(evaluation.FIXTURES, 'bilingual', path)


@pytest.mark.parametrize('defect', [
    'unknown_reference', 'duplicate_document', 'duplicate_case', 'duplicate_gold',
    'no_positive', 'no_negative', 'query_limit', 'wrong_version',
    'not_synthetic', 'extra_case_field', 'blank_case_id', 'unsupported_language',
    'extra_root_field', 'empty_documents', 'empty_cases', 'boolean_version',
    'too_many_cases', 'too_many_documents',
])
def test_invalid_gold_cannot_produce_a_passing_evaluation(tmp_path, monkeypatch, defect):
    data = valid_fixture()
    if defect == 'unknown_reference':
        # At k=1 the old gate passed despite this impossible second label.
        data['cases'][0]['relevant_ids'].append('missing-document')
    elif defect == 'duplicate_document':
        data['documents'].append(deepcopy(data['documents'][0]))
    elif defect == 'duplicate_case':
        data['cases'].append(deepcopy(data['cases'][0]))
    elif defect == 'duplicate_gold':
        data['cases'][0]['relevant_ids'].append('museum')
    elif defect == 'no_positive':
        data['cases'][0]['relevant_ids'] = []
    elif defect == 'no_negative':
        data['cases'][1]['relevant_ids'] = ['museum']
    elif defect == 'query_limit':
        data['cases'][0]['query']['limit'] = 1
    elif defect == 'wrong_version':
        data['version'] = 2
    elif defect == 'not_synthetic':
        data['synthetic'] = False
    elif defect == 'extra_case_field':
        data['cases'][0]['expected_ids'] = ['not-a-supported-label-field']
    elif defect == 'blank_case_id':
        data['cases'][0]['id'] = ' '
    elif defect == 'unsupported_language':
        data['cases'][0]['language'] = 'unknown'
    elif defect == 'extra_root_field':
        data['expected'] = 'ignored-data-must-not-be-accepted'
    elif defect == 'empty_documents':
        data['documents'] = []
    elif defect == 'empty_cases':
        data['cases'] = []
    elif defect == 'boolean_version':
        data['version'] = True
    elif defect == 'too_many_cases':
        data['cases'] = [
            {**deepcopy(data['cases'][0]), 'id': f'positive.{i}'} for i in range(2000)
        ] + [data['cases'][1]]
    elif defect == 'too_many_documents':
        data['documents'] += [
            {**deepcopy(data['documents'][0]), 'document_id': f'extra.{i}'} for i in range(500)
        ]
    write_fixture(tmp_path, monkeypatch, data)
    with pytest.raises(ValueError):
        evaluation.evaluate(bilingual_aliases=True, k=1)


@pytest.mark.parametrize('check', [False, True])
def test_invalid_fixture_cli_reports_input_error_without_success_metrics(tmp_path, monkeypatch, capsys, check):
    data = valid_fixture()
    data['cases'][0]['relevant_ids'].append('missing-document')
    write_fixture(tmp_path, monkeypatch, data)
    assert evaluation.main(['--check'] if check else []) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['error']['code'] == 'invalid_fixture'
    assert 'bilingual' not in report
    assert 'default' not in report


def test_invalid_json_produces_structured_input_error(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'broken.json'
    path.write_text('{"version":', encoding='utf-8')
    monkeypatch.setitem(evaluation.FIXTURES, 'bilingual', path)
    assert evaluation.main(['--check']) == 2
    assert json.loads(capsys.readouterr().out)['error']['code'] == 'invalid_fixture'
