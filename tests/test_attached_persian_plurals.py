"""Explicit attached plural equivalents, with no general suffix stripping."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.assistant.demo import main
from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


FIXTURE = json.loads((Path(__file__).resolve().parents[1] /
    'evaluation/retrieval_persian_plurals_v1.json').read_text(encoding='utf-8'))
DOCUMENTS = tuple(TravelKnowledgeDocumentV1.model_validate(item) for item in FIXTURE['documents'])


@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda case: case['id'])
def test_attached_plural_results_equal_explicit_relevance_labels(case):
    retriever = InMemoryTravelKnowledgeRetriever(DOCUMENTS, bilingual_aliases=True)
    hits = retriever.retrieve(RetrievalQueryV1(**case['query'], limit=3)).hits
    assert {hit.document.document_id for hit in hits} == set(case['relevant_ids'])


def test_default_does_not_translate_attached_plural():
    result = InMemoryTravelKnowledgeRetriever(DOCUMENTS).retrieve(
        RetrievalQueryV1(text='موزهها در تهران', city='Tehran'),
    )
    assert [hit.document.document_id for hit in result.hits] == ['museum.fa']


def test_plural_suite_reports_recall_gain_without_negative_regressions():
    from tools.evaluate_retrieval import evaluate

    baseline = evaluate(bilingual_aliases=False, suite='persian-plurals')
    enhanced = evaluate(bilingual_aliases=True, suite='persian-plurals')
    assert baseline['metrics']['recall_at_k'] == pytest.approx(1 / 3)
    assert enhanced['metrics']['recall_at_k'] == 1.0
    assert enhanced['metrics']['returned_precision'] == 1.0
    assert enhanced['metrics']['negative_abstention'] == 1.0
    assert enhanced['metrics']['total'] == 28


def test_evaluation_cli_selects_plural_suite():
    result = subprocess.run(
        [sys.executable, '-m', 'tools.evaluate_retrieval', '--suite', 'persian-plurals'],
        check=True, capture_output=True, encoding='utf-8',
    )
    report = json.loads(result.stdout)
    assert report['bilingual']['suite'] == 'persian-plurals'
    assert report['bilingual']['metrics']['total'] == 28
    assert report['bilingual']['metrics']['recall_at_k'] == 1.0


def test_attached_plural_reaches_public_demo_with_attribution(capsys):
    assert main(['موزههای تهران', '--country', 'IR', '--city', 'تهران',
                 '--bilingual-aliases', '--format', 'json']) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer['status'] == 'provisional'
    assert [item['document_id'] for item in answer['evidence']] == ['ir.tehran.destination']
    assert answer['needs_verification'] is True
