from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.contract import KnowledgeCategory, TravelKnowledgeDocumentV1


class RetrievalQueryV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    text: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    category: KnowledgeCategory | None = None


class RetrievalHitV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    document: TravelKnowledgeDocumentV1
    score: float = Field(ge=0.0, le=1.0)


class RetrievalResultV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    query: RetrievalQueryV1
    hits: tuple[RetrievalHitV1, ...] = ()


class TravelKnowledgeRetriever(Protocol):
    def retrieve(
        self,
        query: RetrievalQueryV1,
    ) -> RetrievalResultV1:
        ...


__all__ = [
    "RetrievalHitV1",
    "RetrievalQueryV1",
    "RetrievalResultV1",
    "TravelKnowledgeRetriever",
]
