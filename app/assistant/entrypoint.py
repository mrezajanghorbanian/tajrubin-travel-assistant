"""Bounded offline entry point for knowledge questions and draft readiness."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.assistant.demo import DEFAULT_KNOWLEDGE_ROOT, load_local_knowledge_pack
from app.assistant.grounded_qa import TravelAnswerV1, TravelQuestionV1, answer_travel_question
from app.assistant.planning_readiness import PlanningReadinessV1, analyze_planning_request
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


class LocalAssistantResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    response_version: Literal["1.0"] = "1.0"
    kind: Literal["knowledge_answer", "planning_readiness"]
    knowledge: TravelAnswerV1 | None = None
    planning: PlanningReadinessV1 | None = None
    live_verified: Literal[False] = False
    needs_verification: Literal[True] = True

    @model_validator(mode="after")
    def require_one_matching_branch(self) -> "LocalAssistantResponseV1":
        if self.kind == "knowledge_answer":
            valid = self.knowledge is not None and self.planning is None
        else:
            valid = (
                self.knowledge is None and self.planning is not None
                and self.planning.status != "not_planning"
            )
        if not valid:
            raise ValueError("Response must contain exactly one matching branch")
        return self


def handle_local_request(
    request: TravelQuestionV1,
    *,
    knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
) -> LocalAssistantResponseV1:
    """Route without network calls, persistent state or signed-catalog access."""
    planning = analyze_planning_request(request.question)
    if planning.status != "not_planning":
        if request.city is not None or request.country_code is not None:
            raise ValueError(
                "City/country filters apply only to knowledge questions; "
                "include planning destinations in the request text"
            )
        return LocalAssistantResponseV1(kind="planning_readiness", planning=planning)

    documents = load_local_knowledge_pack(knowledge_root)
    answer = answer_travel_question(
        request, InMemoryTravelKnowledgeRetriever(documents, bilingual_aliases=True),
    )
    return LocalAssistantResponseV1(kind="knowledge_answer", knowledge=answer)


def _print_text(result: LocalAssistantResponseV1, *, persian: bool) -> None:
    if result.knowledge is not None:
        print(result.knowledge.answer)
        for evidence in result.knowledge.evidence:
            print(f"[{evidence.document_id}] {evidence.document_title}")
            if evidence.last_reviewed_at:
                print(evidence.last_reviewed_at)
            for url in evidence.external_urls:
                print(url)
    elif result.planning is not None:
        if result.planning.clarification_question:
            print(result.planning.clarification_question)
        else:
            print(
                "جزئیات اولیه سفر آماده است؛ برای برنامه بازدید، شواهد تاریخ‌دار "
                "مکان‌ها و زمان مسیر لازم است."
                if persian else
                "Draft details are ready. A visit schedule still requires dated "
                "attraction evidence and travel-time inputs."
            )
    print("اطلاعات زنده سفر تأیید نشده است." if persian else "Live travel details have not been verified.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="Persian or English travel request")
    parser.add_argument("--country", default=None, help="Country filter for knowledge questions")
    parser.add_argument("--city", default=None, help="City filter for knowledge questions")
    parser.add_argument("--max-results", type=int, default=3, help="Knowledge results (1 to 5)")
    parser.add_argument("--knowledge-root", type=Path, default=DEFAULT_KNOWLEDGE_ROOT)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        request = TravelQuestionV1(
            question=args.request, country_code=args.country,
            city=args.city, max_results=args.max_results,
        )
        result = handle_local_request(request, knowledge_root=args.knowledge_root)
    except ValueError as exc:
        print(f"Local assistant input error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(result.model_dump_json(indent=2))
    else:
        _print_text(result, persian=re.search(r"[\u0600-\u06ff]", request.question) is not None)
    return 0


__all__ = ["LocalAssistantResponseV1", "handle_local_request", "main"]
