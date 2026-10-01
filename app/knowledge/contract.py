from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KnowledgeCategory = Literal[
    "destination",
    "attraction",
    "experience",
    "food",
    "culture",
    "transport",
    "practical",
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class TravelKnowledgeSourceV1(_StrictFrozenModel):
    """Source provenance for one travel knowledge document."""

    title: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2048)
    publisher: str | None = Field(default=None, max_length=300)
    accessed_at: date | None = None


class TravelKnowledgeDocumentV1(_StrictFrozenModel):
    """Canonical source document for travel knowledge ingestion."""

    knowledge_version: Literal["1.0"] = "1.0"

    document_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )

    country_code: str = Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    country_name: str = Field(min_length=1, max_length=120)

    region: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=160)

    category: KnowledgeCategory

    title: str = Field(min_length=1, max_length=300)

    summary: str = Field(min_length=1, max_length=2000)

    content: str = Field(min_length=1, max_length=50_000)

    tags: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=40,
    )

    languages: tuple[str, ...] = Field(
        default=("en",),
        min_length=1,
        max_length=10,
    )

    sources: tuple[TravelKnowledgeSourceV1, ...] = Field(
        default_factory=tuple,
        max_length=20,
    )

    last_reviewed_at: date | None = None


__all__ = [
    "KnowledgeCategory",
    "TravelKnowledgeDocumentV1",
    "TravelKnowledgeSourceV1",
]