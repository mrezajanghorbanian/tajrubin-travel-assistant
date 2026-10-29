"""Reproducible synthetic retrieval evaluation; no network or model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


FIXTURE = Path(__file__).resolve().parents[1] / "evaluation/retrieval_bilingual_v1.json"
FIXTURES = {
    "bilingual": FIXTURE,
    "persian-plurals": FIXTURE.with_name("retrieval_persian_plurals_v1.json"),
}
K = 3


def _validate_k(k: int) -> None:
    if type(k) is not int or not 1 <= k <= 20:
        raise ValueError("k must be an integer from 1 to 20")


def summarize(cases: list[dict], *, k: int) -> dict:
    """Keep positive recall separate from negative abstention and precision."""
    _validate_k(k)
    cases = [{**case, "retrieved_ids": case["retrieved_ids"][:k]} for case in cases]
    positives = [case for case in cases if case["relevant_ids"]]
    negatives = [case for case in cases if not case["relevant_ids"]]

    def true_positives(case: dict) -> int:
        return len(set(case["retrieved_ids"]) & set(case["relevant_ids"]))

    returned = sum(len(case["retrieved_ids"]) for case in cases)
    relevant_returned = sum(true_positives(case) for case in cases)
    return {
        "total": len(cases),
        "positive_queries": len(positives),
        "negative_queries": len(negatives),
        "returned_precision": relevant_returned / returned if returned else None,
        "precision_at_k": (
            sum(true_positives(case) / k for case in positives) / len(positives)
            if positives else None
        ),
        "recall_at_k": (
            sum(true_positives(case) / len(case["relevant_ids"]) for case in positives)
            / len(positives) if positives else None
        ),
        "hit_at_1": (
            sum(bool(case["retrieved_ids"]) and
                case["retrieved_ids"][0] in case["relevant_ids"] for case in positives)
            / len(positives) if positives else None
        ),
        "mrr_at_k": (
            sum(next((
                1 / rank for rank, identifier in enumerate(case["retrieved_ids"], 1)
                if identifier in case["relevant_ids"]
            ), 0.0) for case in positives) / len(positives)
            if positives else None
        ),
        "negative_abstention": (
            sum(not case["retrieved_ids"] for case in negatives) / len(negatives)
            if negatives else None
        ),
    }


def assess(cases: list[dict], *, k: int) -> dict:
    """Require exact synthetic relevance coverage up to the selected cutoff."""
    _validate_k(k)
    failures = []
    for case in cases:
        returned = case["retrieved_ids"]
        relevant = set(case["relevant_ids"])
        selected = set(returned[:k])
        unexpected = sorted(selected - relevant)
        missing = max(0, min(k, len(relevant)) - len(selected & relevant))
        duplicates = sorted(identifier for identifier, count in Counter(returned).items() if count > 1)
        over_limit = len(returned) > k
        if unexpected or missing or duplicates or over_limit:
            failures.append({
                "case_id": case["id"],
                "unexpected_ids": unexpected,
                "missing_relevant_count": missing,
                "duplicate_ids": duplicates,
                "over_limit": over_limit,
            })
    errors = [] if cases else ["empty_case_set"]
    return {
        "policy": "exact_synthetic_relevance_at_k_v1",
        "cases_checked": len(cases),
        "passed": not errors and not failures,
        "errors": errors,
        "failures": failures,
    }


def _validate_fixture(fixture: object) -> tuple[TravelKnowledgeDocumentV1, ...]:
    """Validate gold-data structure without deriving labels from retrieval."""
    if not isinstance(fixture, dict) or set(fixture) != {"version", "synthetic", "documents", "cases"}:
        raise ValueError("Fixture must contain only version, synthetic, documents and cases")
    if type(fixture["version"]) is not int or fixture["version"] != 1:
        raise ValueError("Unsupported fixture version")
    if fixture["synthetic"] is not True:
        raise ValueError("Fixture must explicitly declare synthetic=true")
    payload = fixture["documents"]
    if not isinstance(payload, list) or not 1 <= len(payload) <= 500:
        raise ValueError("Fixture must contain 1 to 500 documents")
    documents = tuple(
        TravelKnowledgeDocumentV1.model_validate(item) for item in payload
    )
    document_ids = {document.document_id for document in documents}
    if len(document_ids) != len(documents):
        raise ValueError("Duplicate fixture document IDs")
    cases = fixture["cases"]
    if not isinstance(cases, list) or not 2 <= len(cases) <= 2000:
        raise ValueError("Fixture must contain 2 to 2000 cases")
    case_ids: set[str] = set()
    positives = 0
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "language", "query", "relevant_ids"}:
            raise ValueError("Case must contain only id, language, query and relevant_ids")
        identifier = case["id"]
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 160:
            raise ValueError("Case ID must be a nonblank string of at most 160 characters")
        if identifier in case_ids:
            raise ValueError("Duplicate fixture case ID: " + identifier)
        case_ids.add(identifier)
        if case["language"] not in ("en", "fa"):
            raise ValueError("Case language must be en or fa: " + identifier)
        query = case["query"]
        if not isinstance(query, dict) or "limit" in query:
            raise ValueError("Case query must be a mapping without limit: " + identifier)
        RetrievalQueryV1.model_validate(query)
        labels = case["relevant_ids"]
        if not isinstance(labels, list) or len(labels) > 500 or not all(isinstance(label, str) for label in labels):
            raise ValueError("Relevant IDs must be a list of at most 500 strings: " + identifier)
        if len(set(labels)) != len(labels):
            raise ValueError("Duplicate relevant IDs: " + identifier)
        if not set(labels).issubset(document_ids):
            raise ValueError("Unknown relevant document IDs: " + identifier)
        positives += bool(labels)
    if not 0 < positives < len(cases):
        raise ValueError("Fixture requires both positive and negative cases")
    return documents


def evaluate(*, bilingual_aliases: bool, suite: str = "bilingual", k: int = K) -> dict:
    _validate_k(k)
    fixture_bytes = FIXTURES[suite].read_bytes()
    fixture = json.loads(fixture_bytes)
    documents = _validate_fixture(fixture)
    retriever = InMemoryTravelKnowledgeRetriever(
        documents, bilingual_aliases=bilingual_aliases,
    )
    outcomes = []
    for case in fixture["cases"]:
        result = retriever.retrieve(RetrievalQueryV1(**case["query"], limit=k))
        outcomes.append({
            **case,
            "retrieved_ids": [hit.document.document_id for hit in result.hits],
        })
    return {
        "suite": suite,
        "fixture_version": fixture["version"],
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "k": k,
        "bilingual_aliases": bilingual_aliases,
        "metrics": summarize(outcomes, k=k),
        "gate": assess(outcomes, k=k),
        "by_language": {
            language: summarize(
                [case for case in outcomes if case["language"] == language], k=k,
            )
            for language in sorted({case["language"] for case in outcomes})
        },
        "cases": outcomes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=tuple(FIXTURES), default="bilingual")
    parser.add_argument("--k", type=int, choices=range(1, 21), default=K)
    parser.add_argument("--check", action="store_true", help="Fail if the bilingual synthetic gate fails")
    args = parser.parse_args(argv)
    try:
        report = {
            "synthetic": True,
            "default": evaluate(bilingual_aliases=False, suite=args.suite, k=args.k),
            "bilingual": evaluate(bilingual_aliases=True, suite=args.suite, k=args.k),
        }
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": "invalid_fixture", "message": str(exc)}}))
        return 2
    print(json.dumps(report, indent=2))
    return int(args.check and not report["bilingual"]["gate"]["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
