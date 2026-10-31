"""Bounded palace/mosque translations, measured against explicit judgments."""
import json
import subprocess
import sys

import pytest

from tools.evaluate_retrieval import FIXTURES, evaluate


CASES = json.loads(FIXTURES["palace-mosque"].read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_exact_reviewed_translation_results(case):
    report = evaluate(bilingual_aliases=True, suite="palace-mosque")
    result = next(item for item in report["cases"] if item["id"] == case["id"])
    assert set(result["retrieved_ids"]) == set(case["relevant_ids"])


def test_new_translations_improve_recall_without_changing_default_or_negatives():
    baseline = evaluate(bilingual_aliases=False, suite="palace-mosque")
    bilingual = evaluate(bilingual_aliases=True, suite="palace-mosque")
    assert baseline["metrics"]["recall_at_k"] == 0.5
    assert bilingual["metrics"]["recall_at_k"] == 1
    for report in (baseline, bilingual):
        assert report["metrics"]["returned_precision"] == 1
        assert report["metrics"]["negative_abstention"] == 1
    assert bilingual["gate"]["passed"] is True


def test_cli_runs_new_suite_gate():
    result = subprocess.run(
        [sys.executable, "-m", "tools.evaluate_retrieval", "--suite", "palace-mosque", "--check"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert json.loads(result.stdout)["bilingual"]["gate"]["cases_checked"] == 28


def test_missing_translations_fail_unchanged_gold_gate(monkeypatch, capsys):
    from app.retrieval.curated_aliases import CURATED_TRAVEL_TERMS
    from tools.evaluate_retrieval import main

    for term in ("palace", "کاخ", "mosque", "مسجد"):
        monkeypatch.delitem(CURATED_TRAVEL_TERMS, term)
    assert main(["--suite", "palace-mosque", "--check"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["bilingual"]["metrics"]["recall_at_k"] == 0.5
    assert len(report["bilingual"]["gate"]["failures"]) == 12
