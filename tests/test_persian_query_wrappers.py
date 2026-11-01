"""Polite query words must not erase factual qualifiers or empty-query guards."""
import json
import subprocess
import sys

import pytest

from tools.evaluate_retrieval import FIXTURES, evaluate


CASES = json.loads(FIXTURES["persian-query-wrappers"].read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def outcomes():
    report = evaluate(bilingual_aliases=True, suite="persian-query-wrappers")
    return {case["id"]: case["retrieved_ids"] for case in report["cases"]}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_explicit_wrapper_judgments(case, outcomes):
    assert set(outcomes[case["id"]]) == set(case["relevant_ids"])


@pytest.mark.parametrize("question", ["درباره کاخ گلستان", "لطفا کاخ گلستان", "لطفاً درباره کاخ گلستان"])
def test_polite_persian_question_reaches_unified_cli_with_source(question):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "app.assistant", question, "--format", "json"],
        check=True, capture_output=True, encoding="utf-8",
    )
    payload = json.loads(result.stdout)
    assert payload["kind"] == "knowledge_answer"
    assert payload["knowledge"]["status"] == "provisional"
    assert payload["needs_verification"] is True
    assert [item["document_id"] for item in payload["knowledge"]["evidence"]] == ["ir.tehran.golestan-palace"]
    assert payload["knowledge"]["evidence"][0]["external_urls"] == ["https://whc.unesco.org/en/list/1422/"]


def test_default_lexical_mode_still_rejects_unmatched_persian_wrappers():
    report = evaluate(bilingual_aliases=False, suite="persian-query-wrappers")
    for case in report["cases"]:
        if case["language"] == "fa":
            assert case["retrieved_ids"] == []


def test_wrapper_suite_exposes_recall_and_abstention():
    report = evaluate(bilingual_aliases=True, suite="persian-query-wrappers")
    assert report["metrics"]["recall_at_k"] == 1
    assert report["metrics"]["negative_abstention"] == 1
    assert report["metrics"]["returned_precision"] == 1
    assert report["metrics"]["positive_queries"] == 12
    assert report["metrics"]["negative_queries"] == 18
    assert report["gate"]["passed"] is True


@pytest.mark.parametrize(("question", "filters"), [
    ("لطفاً درباره قیمت بلیت کاخ گلستان", {}),
    ("لطفاً درباره ساعت بازدید کاخ گلستان", {}),
    ("لطفاً نه کاخ گلستان", {}),
    ("لطفاً درباره", {}),
    ("لطفاً درباره", {"city": "Tehran"}),
    ("درباره کاخ گلستان", {"city": "Yazd"}),
    ("لطفاً کاخ گلستان", {"country_code": "GB"}),
])
def test_real_corpus_keeps_unsupported_claims_negation_and_filters(question, filters):
    from app.assistant.entrypoint import handle_local_request
    from app.assistant.grounded_qa import TravelQuestionV1

    result = handle_local_request(TravelQuestionV1(question=question, **filters))
    assert result.kind == "knowledge_answer"
    assert result.knowledge.status == "insufficient_evidence"
    assert result.knowledge.evidence == ()
    assert result.needs_verification is True


def test_removing_wrapper_support_fails_unchanged_judgments(monkeypatch, capsys):
    from app.retrieval import in_memory
    from tools.evaluate_retrieval import main

    monkeypatch.setattr(in_memory, "_BILINGUAL_QUERY_STOPWORDS", frozenset())
    assert main(["--suite", "persian-query-wrappers", "--check"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["bilingual"]["metrics"]["recall_at_k"] == 0.5
    assert len(report["bilingual"]["gate"]["failures"]) == 6
