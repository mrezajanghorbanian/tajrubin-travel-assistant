"""Real corpus, frozen development judgments and fail-closed evaluation."""
import json
import shutil
import subprocess
import sys

import pytest

from app.assistant.demo import DEFAULT_KNOWLEDGE_ROOT
from tools import evaluate_knowledge_pack as evaluator


@pytest.mark.parametrize("k", [1, 3, 5])
def test_repository_corpus_matches_explicit_judgments(k):
    report = evaluator.evaluate(k=k)
    assert report["document_count"] == 4
    assert report["independent_benchmark"] is False
    assert report["live_verified"] is False
    assert report["bilingual"]["gate"]["passed"] is True
    for language in ("en", "fa"):
        metrics = report["bilingual"]["by_language"][language]
        assert metrics["positive_queries"] == metrics["negative_queries"] == 8
        assert metrics["negative_abstention"] == metrics["returned_precision"] == 1.0
        assert metrics["recall_at_k"] == pytest.approx(11 / 12 if k == 1 else 1)


def test_cli_runs_real_corpus_gate():
    result = subprocess.run(
        [sys.executable, "-m", "tools.evaluate_knowledge_pack", "--check"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    report = json.loads(result.stdout)
    assert report["bilingual"]["gate"]["cases_checked"] == 32
    assert report["bilingual"]["metrics"]["precision_at_k"] == pytest.approx(5 / 12)
    assert len(report["corpus_sha256"]) == len(report["fixture_sha256"]) == 64


@pytest.mark.parametrize("mutation", ["unknown_id", "duplicate_case", "limit", "no_negatives", "extra", "version"])
def test_invalid_judgments_fail_without_metrics(tmp_path, monkeypatch, capsys, mutation):
    fixture = json.loads(evaluator.FIXTURE.read_text(encoding="utf-8"))
    if mutation == "unknown_id":
        fixture["cases"][0]["relevant_ids"].append("missing")
    elif mutation == "duplicate_case":
        fixture["cases"][1]["id"] = fixture["cases"][0]["id"]
    elif mutation == "limit":
        fixture["cases"][0]["query"]["limit"] = 1
    elif mutation == "no_negatives":
        fixture["cases"] = [case for case in fixture["cases"] if case["relevant_ids"]]
    elif mutation == "extra":
        fixture["synthetic"] = True
    else:
        fixture["version"] = True
    path = tmp_path / "judgments.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setattr(evaluator, "FIXTURE", path)
    assert evaluator.main(["--check"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"error"}
    assert report["error"]["code"] == "invalid_evaluation_input"


def test_wrong_existing_label_fails_gate_and_report_only_preserves_failure(tmp_path, monkeypatch, capsys):
    fixture = json.loads(evaluator.FIXTURE.read_text(encoding="utf-8"))
    fixture["cases"][0]["relevant_ids"] = ["ir.yazd.historic-city"]
    path = tmp_path / "judgments.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setattr(evaluator, "FIXTURE", path)
    assert evaluator.main(["--check"]) == 1
    report = json.loads(capsys.readouterr().out)
    failure = report["bilingual"]["gate"]["failures"][0]
    assert failure["case_id"] == "golestan-en"
    assert failure["unexpected_ids"] == ["ir.tehran.golestan-palace"]
    assert failure["missing_relevant_count"] == 1
    assert evaluator.main([]) == 0
    assert json.loads(capsys.readouterr().out)["bilingual"]["gate"]["passed"] is False


def test_content_regression_changes_fingerprint_and_fails_unchanged_gold(tmp_path):
    baseline = evaluator.evaluate()
    root = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KNOWLEDGE_ROOT, root)
    path = root / "iran/attractions/golestan-palace.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Golestan", "Other").replace("گلستان", "دیگر"), encoding="utf-8")
    regressed = evaluator.evaluate(knowledge_root=root)
    assert regressed["fixture_sha256"] == baseline["fixture_sha256"]
    assert regressed["corpus_sha256"] != baseline["corpus_sha256"]
    assert regressed["bilingual"]["gate"]["passed"] is False
    assert regressed["bilingual"]["metrics"]["recall_at_k"] < 1
