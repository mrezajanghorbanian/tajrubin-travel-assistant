"""Reproducible synthetic retrieval evaluation; no network or model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
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


def summarize(cases: list[dict], *, k: int) -> dict:
    """Keep positive recall separate from negative abstention and precision."""
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
        "negative_abstention": (
            sum(not case["retrieved_ids"] for case in negatives) / len(negatives)
            if negatives else None
        ),
    }


def evaluate(*, bilingual_aliases: bool, suite: str = "bilingual") -> dict:
    fixture_bytes = FIXTURES[suite].read_bytes()
    fixture = json.loads(fixture_bytes)
    documents = tuple(
        TravelKnowledgeDocumentV1.model_validate(item) for item in fixture["documents"]
    )
    retriever = InMemoryTravelKnowledgeRetriever(
        documents, bilingual_aliases=bilingual_aliases,
    )
    outcomes = []
    for case in fixture["cases"]:
        result = retriever.retrieve(RetrievalQueryV1(**case["query"], limit=K))
        outcomes.append({
            **case,
            "retrieved_ids": [hit.document.document_id for hit in result.hits],
        })
    return {
        "suite": suite,
        "fixture_version": fixture["version"],
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "k": K,
        "bilingual_aliases": bilingual_aliases,
        "metrics": summarize(outcomes, k=K),
        "by_language": {
            language: summarize(
                [case for case in outcomes if case["language"] == language], k=K,
            )
            for language in sorted({case["language"] for case in outcomes})
        },
        "cases": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=tuple(FIXTURES), default="bilingual")
    args = parser.parse_args()
    print(json.dumps({
        "synthetic": True,
        "default": evaluate(bilingual_aliases=False, suite=args.suite),
        "bilingual": evaluate(bilingual_aliases=True, suite=args.suite),
    }, indent=2))


if __name__ == "__main__":
    main()
