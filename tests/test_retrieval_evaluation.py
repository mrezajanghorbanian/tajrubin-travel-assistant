"""Hand-counted metric checks and fixed synthetic relevance judgments."""
import json
import subprocess
import sys

import pytest


def test_metrics_count_irrelevant_results_and_negative_false_positives():
    from tools.evaluate_retrieval import summarize

    report = summarize([
        {'language': 'en', 'relevant_ids': ['a', 'b'], 'retrieved_ids': ['a', 'noise']},
        {'language': 'fa', 'relevant_ids': ['c'], 'retrieved_ids': []},
        {'language': 'en', 'relevant_ids': [], 'retrieved_ids': ['noise']},
        {'language': 'fa', 'relevant_ids': [], 'retrieved_ids': []},
    ], k=3)
    assert report['returned_precision'] == pytest.approx(1 / 3)
    assert report['precision_at_k'] == pytest.approx(1 / 6)
    assert report['recall_at_k'] == pytest.approx(1 / 4)
    assert report['hit_at_1'] == 0.5
    assert report['negative_abstention'] == 0.5


def test_metrics_do_not_count_successful_abstention_as_positive_recall():
    from tools.evaluate_retrieval import summarize

    report = summarize([
        {'language': 'fa', 'relevant_ids': [], 'retrieved_ids': []},
    ], k=3)
    assert report['negative_abstention'] == 1.0
    assert report['returned_precision'] is None
    assert report['recall_at_k'] is None
    assert report['precision_at_k'] is None
    assert report['hit_at_1'] is None


def test_frozen_bilingual_cases_have_exact_results_and_safe_filters():
    from tools.evaluate_retrieval import evaluate

    report = evaluate(bilingual_aliases=True)
    assert report['metrics']['recall_at_k'] == 1.0
    assert report['metrics']['returned_precision'] == 1.0
    assert report['metrics']['negative_abstention'] == 1.0
    for case in report['cases']:
        assert set(case['retrieved_ids']) == set(case['relevant_ids']), case
    assert report['by_language']['fa']['recall_at_k'] == 1.0
    assert report['by_language']['en']['recall_at_k'] == 1.0


def test_evaluation_cli_compares_default_and_opt_in_without_network():
    result = subprocess.run(
        [sys.executable, '-m', 'tools.evaluate_retrieval'],
        check=True, capture_output=True, text=True, encoding='utf-8',
    )
    report = json.loads(result.stdout)
    assert report['synthetic'] is True
    assert report['bilingual']['metrics']['recall_at_k'] > report['default']['metrics']['recall_at_k']
    assert report['bilingual']['metrics']['negative_abstention'] == 1.0
