"""Cutoff-aware ranking evaluation with independently hand-counted examples."""
import json
import subprocess
import sys

import pytest

from tools.evaluate_retrieval import evaluate, summarize


@pytest.mark.parametrize(('k', 'precision', 'recall', 'returned_precision', 'mrr'), [
    (1, 0.5, 0.5, 1 / 3, 0.5),
    (2, 0.5, 0.75, 2 / 5, 0.75),
    (3, 0.5, 1.0, 3 / 6, 0.75),
])
def test_metrics_ignore_results_beyond_cutoff(k, precision, recall, returned_precision, mrr):
    cases = [
        {'relevant_ids': ['a', 'b'], 'retrieved_ids': ['noise', 'a', 'b']},
        {'relevant_ids': ['c'], 'retrieved_ids': ['c', 'noise']},
        {'relevant_ids': [], 'retrieved_ids': ['bad']},
    ]
    report = summarize(cases, k=k)
    assert report['precision_at_k'] == pytest.approx(precision)
    assert report['recall_at_k'] == pytest.approx(recall)
    assert report['returned_precision'] == pytest.approx(returned_precision)
    assert report['mrr_at_k'] == pytest.approx(mrr)
    assert report['hit_at_1'] == 0.5
    assert report['negative_abstention'] == 0.0
    assert cases[0]['retrieved_ids'] == ['noise', 'a', 'b']


def test_mrr_counts_unretrieved_positive_as_zero():
    report = summarize([
        {'relevant_ids': ['a'], 'retrieved_ids': ['noise', 'a']},
        {'relevant_ids': ['b'], 'retrieved_ids': []},
        {'relevant_ids': [], 'retrieved_ids': []},
    ], k=3)
    assert report['mrr_at_k'] == 0.25
    assert report['negative_abstention'] == 1.0


def test_mrr_is_undefined_without_positive_queries():
    assert summarize([{'relevant_ids': [], 'retrieved_ids': []}], k=3)['mrr_at_k'] is None


@pytest.mark.parametrize('k', [0, 21, True, 1.5])
@pytest.mark.parametrize('target', ['summarize', 'evaluate'])
def test_cutoff_rejects_values_outside_retrieval_contract(k, target):
    with pytest.raises(ValueError, match='k must be an integer from 1 to 20'):
        if target == 'summarize':
            summarize([], k=k)
        else:
            evaluate(bilingual_aliases=True, k=k)


@pytest.mark.parametrize(('suite', 'k', 'recall', 'precision'), [
    ('bilingual', 1, 31 / 36, 1.0),
    ('bilingual', 3, 1.0, 23 / 54),
    ('bilingual', 5, 1.0, 23 / 90),
    ('persian-plurals', 1, 0.5, 1.0),
    ('persian-plurals', 3, 1.0, 2 / 3),
    ('persian-plurals', 5, 1.0, 2 / 5),
])
def test_real_retrieval_respects_cutoff_with_fixed_judgments(suite, k, recall, precision):
    report = evaluate(bilingual_aliases=True, suite=suite, k=k)
    assert report['k'] == k
    assert report['metrics']['recall_at_k'] == pytest.approx(recall)
    assert report['metrics']['precision_at_k'] == pytest.approx(precision)
    assert report['metrics']['returned_precision'] == 1.0
    assert report['metrics']['mrr_at_k'] == 1.0
    assert report['metrics']['negative_abstention'] == 1.0
    assert all(len(case['retrieved_ids']) <= k for case in report['cases'])


def test_cli_threads_cutoff_into_both_retrievers():
    result = subprocess.run(
        [sys.executable, '-m', 'tools.evaluate_retrieval', '--suite', 'persian-plurals', '--k', '1'],
        check=True, capture_output=True, encoding='utf-8',
    )
    report = json.loads(result.stdout)
    assert report['default']['k'] == report['bilingual']['k'] == 1
    assert report['bilingual']['metrics']['recall_at_k'] == 0.5
    assert report['bilingual']['metrics']['precision_at_k'] == 1.0
    assert report['default']['metrics']['recall_at_k'] == pytest.approx(1 / 3)


@pytest.mark.parametrize('k', ['0', '21'])
def test_cli_invalid_cutoff_exits_without_json_report(k):
    result = subprocess.run(
        [sys.executable, '-m', 'tools.evaluate_retrieval', '--k', k],
        capture_output=True, encoding='utf-8',
    )
    assert result.returncode == 2
    assert result.stdout == ''
