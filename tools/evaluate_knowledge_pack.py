"""Offline development retrieval evaluation over checked-in Markdown content."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.assistant.demo import DEFAULT_KNOWLEDGE_ROOT, load_local_knowledge_pack
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever
from tools.evaluate_retrieval import _validate_k, assess, summarize, validate_cases


FIXTURE = Path(__file__).resolve().parents[1] / "evaluation/knowledge_pack_v1.json"


def evaluate(*, k: int = 3, knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT) -> dict:
    _validate_k(k)
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    if not isinstance(fixture, dict) or set(fixture) != {"version", "corpus", "cases"}:
        raise ValueError("Expected only version, corpus and cases")
    if type(fixture["version"]) is not int or fixture["version"] != 1:
        raise ValueError("Unsupported judgment version")
    if fixture["corpus"] != "repository_knowledge_markdown":
        raise ValueError("Unsupported corpus")
    documents = load_local_knowledge_pack(knowledge_root)
    validate_cases(fixture["cases"], document_ids={doc.document_id for doc in documents})
    # Fingerprint the actual validated retrieval inputs, including source metadata.
    corpus_bytes = json.dumps(
        [doc.model_dump(mode="json") for doc in sorted(documents, key=lambda doc: doc.document_id)],
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    modes = {}
    for name, enabled in (("default", False), ("bilingual", True)):
        retriever = InMemoryTravelKnowledgeRetriever(documents, bilingual_aliases=enabled)
        outcomes = []
        for case in fixture["cases"]:
            result = retriever.retrieve(RetrievalQueryV1(**case["query"], limit=k))
            outcomes.append({**case, "retrieved_ids": [hit.document.document_id for hit in result.hits]})
        gate = assess(outcomes, k=k)
        gate["policy"] = "exact_repository_relevance_at_k_v1"
        modes[name] = {
            "metrics": summarize(outcomes, k=k), "gate": gate,
            "by_language": {
                language: summarize([case for case in outcomes if case["language"] == language], k=k)
                for language in sorted({case["language"] for case in outcomes})
            },
            "cases": outcomes,
        }
    return {
        "suite": "repository-knowledge", "development_queries": True,
        "independent_benchmark": False, "live_verified": False,
        "fixture_version": fixture["version"], "k": k,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "document_count": len(documents), **modes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, choices=range(1, 21), default=3)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = evaluate(k=args.k)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": "invalid_evaluation_input", "message": str(exc)}}))
        return 2
    print(json.dumps(report, indent=2))
    return int(args.check and not report["bilingual"]["gate"]["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
