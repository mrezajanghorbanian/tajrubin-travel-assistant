"""Offline travel knowledge Q&A demo.

No paid API, network access or language model required. This CLI demonstrates
the retrieval → attributed provisional answer boundary, not itinerary planning.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from app.assistant.grounded_qa import TravelQuestionV1, answer_travel_question
from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.knowledge.loader import (
    TravelKnowledgeLoadError,
    load_travel_knowledge_markdown,
)
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


DEFAULT_KNOWLEDGE_ROOT = (
    Path(__file__).resolve().parents[2] / "knowledge"
)
MAX_KNOWLEDGE_DOCUMENTS = 500


def load_local_knowledge_pack(
    root: Path,
    *,
    max_documents: int = MAX_KNOWLEDGE_DOCUMENTS,
) -> tuple[TravelKnowledgeDocumentV1, ...]:
    """Load a bounded pack deterministically; reject duplicate source IDs."""
    if max_documents < 1:
        raise ValueError("max_documents must be positive")

    if not root.is_dir():
        raise ValueError("Knowledge root does not exist or is not a directory")

    paths = sorted(root.rglob("*.md"))

    if not paths:
        raise ValueError("Knowledge root contains no Markdown source documents")
    if len(paths) > max_documents:
        raise ValueError("Knowledge pack exceeds document-count safety limit")

    documents: list[TravelKnowledgeDocumentV1] = []
    ids: set[str] = set()

    for path in paths:
        if path.is_symlink():
            raise ValueError("Knowledge packs must not contain symlinked documents")

        document = load_travel_knowledge_markdown(path)
        if document.document_id in ids:
            raise ValueError("Duplicate knowledge document_id: " + document.document_id)
        ids.add(document.document_id)
        documents.append(document)

    return tuple(documents)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline source-attributed travel knowledge demo"
    )
    parser.add_argument("question", help="Travel question in natural language")
    parser.add_argument("--country", default=None, help="ISO 3166-1 alpha-2 code")
    parser.add_argument("--city", default=None, help="Optional city filter")
    parser.add_argument(
        "--bilingual-aliases",
        action="store_true",
        help="Enable reviewed Persian/English term and city equivalents",
    )
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        default=DEFAULT_KNOWLEDGE_ROOT,
        help="Local source-document directory (default: repository knowledge/)",
    )
    parser.add_argument(
        "--max-results", type=int, default=3, help="Top matches (1 to 5)"
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text"
    )
    args = parser.parse_args(argv)

    try:
        request = TravelQuestionV1(
            question=args.question,
            country_code=args.country,
            city=args.city,
            max_results=args.max_results,
        )
        documents = load_local_knowledge_pack(args.knowledge_root)
        answer = answer_travel_question(
            request,
            InMemoryTravelKnowledgeRetriever(
                documents, bilingual_aliases=args.bilingual_aliases,
            ),
        )
    except (ValidationError, ValueError, TravelKnowledgeLoadError) as exc:
        print(f"Travel demo input error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(answer.model_dump_json(indent=2))
    else:
        print(answer.answer)
        print("\nEvidence:")
        if answer.evidence:
            for evidence in answer.evidence:
                print(f"- {evidence.document_title} [{evidence.document_id}]")
                if evidence.last_reviewed_at:
                    print(f"  Reviewed: {evidence.last_reviewed_at}")
                for url in evidence.external_urls:
                    print(f"  Source URL: {url}")
        else:
            print("- No relevant documents")
        print("\nStatus: " + answer.status)
        print("Live prices, opening hours and availability are not verified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
