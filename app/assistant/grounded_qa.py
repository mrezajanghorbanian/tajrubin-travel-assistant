"""Deterministic provisional travel Q&A over retrieved knowledge.

First integration slice, not a live-information or autonomous agent.
Untrusted knowledge is returned as attributed data, never as instructions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.contract import RetrievalQueryV1, TravelKnowledgeRetriever


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class TravelQuestionV1(_StrictModel):
    question: str = Field(min_length=3, max_length=2000)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    city: str | None = Field(default=None, min_length=1, max_length=120)
    max_results: int = Field(default=3, ge=1, le=5)


class EvidenceV1(_StrictModel):
    document_id: str
    document_title: str
    external_urls: tuple[str, ...] = ()
    last_reviewed_at: str | None = None


class TravelAnswerV1(_StrictModel):
    status: Literal["provisional", "insufficient_evidence"]
    answer: str
    evidence: tuple[EvidenceV1, ...] = ()
    needs_verification: bool = True


def answer_travel_question(
    request: TravelQuestionV1,
    retriever: TravelKnowledgeRetriever,
) -> TravelAnswerV1:
    """Return bounded, attributed summaries; never fabricate live travel details."""
    matches = retriever.retrieve(
        RetrievalQueryV1(
            text=request.question,
            limit=request.max_results,
            country_code=request.country_code,
            city=request.city,
        )
    )

    if not matches.hits:
        return TravelAnswerV1(
            status="insufficient_evidence",
            answer="I don't have enough relevant travel knowledge to answer reliably.",
        )

    summaries: list[str] = []
    evidence: list[EvidenceV1] = []

    for hit in matches.hits:
        document = hit.document
        summaries.append(f"{document.summary} [{document.document_id}]")
        evidence.append(
            EvidenceV1(
                document_id=document.document_id,
                document_title=document.title,
                external_urls=tuple(
                    source.url
                    for source in document.sources
                    if source.url is not None and source.url.startswith("https://")
                ),
                last_reviewed_at=(
                    document.last_reviewed_at.isoformat()
                    if document.last_reviewed_at
                    else None
                ),
            )
        )

    return TravelAnswerV1(
        status="provisional",
        answer="\n".join(summaries)
        + (
            "\n\nBased on local knowledge documents. Verify current hours, "
            "prices, access conditions and other time-sensitive details."
        ),
        evidence=tuple(evidence),
    )


__all__ = [
    "TravelQuestionV1",
    "EvidenceV1",
    "TravelAnswerV1",
    "answer_travel_question",
]
