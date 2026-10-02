from __future__ import annotations

from typing import runtime_checkable

import pytest
from pydantic import ValidationError

from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import (
    RetrievalHitV1,
    RetrievalQueryV1,
    RetrievalResultV1,
    TravelKnowledgeRetriever,
)


def _document() -> TravelKnowledgeDocumentV1:
    return TravelKnowledgeDocumentV1(
        document_id="ir.tehran.destination",
        country_code="IR",
        country_name="Iran",
        region="Tehran Province",
        city="Tehran",
        category="destination",
        title="Tehran",
        summary="Iran's capital city.",
        content="Tehran is a major cultural and travel destination.",
        tags=("capital", "culture"),
        languages=("en",),
        sources=(),
        last_reviewed_at="2026-10-01",
    )


def test_query_defaults():
    query = RetrievalQueryV1(text="Tehran museums")

    assert query.text == "Tehran museums"
    assert query.limit == 5
    assert query.country_code is None
    assert query.region is None
    assert query.city is None
    assert query.category is None


def test_query_accepts_filters():
    query = RetrievalQueryV1(
        text="museum",
        limit=10,
        country_code="IR",
        region="Tehran Province",
        city="Tehran",
        category="destination",
    )

    assert query.limit == 10
    assert query.country_code == "IR"
    assert query.city == "Tehran"


@pytest.mark.parametrize("limit", [0, 21])
def test_query_rejects_invalid_limit(limit: int):
    with pytest.raises(ValidationError):
        RetrievalQueryV1(
            text="Tehran",
            limit=limit,
        )


def test_query_rejects_empty_text():
    with pytest.raises(ValidationError):
        RetrievalQueryV1(text="   ")


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_hit_rejects_out_of_range_score(score: float):
    with pytest.raises(ValidationError):
        RetrievalHitV1(
            document=_document(),
            score=score,
        )


def test_hit_accepts_normalized_score():
    hit = RetrievalHitV1(
        document=_document(),
        score=0.91,
    )

    assert hit.score == 0.91
    assert hit.document.document_id == "ir.tehran.destination"


def test_result_defaults_to_empty_hits():
    query = RetrievalQueryV1(text="Tehran")

    result = RetrievalResultV1(query=query)

    assert result.query == query
    assert result.hits == ()


def test_result_accepts_hits():
    query = RetrievalQueryV1(text="Tehran")

    hit = RetrievalHitV1(
        document=_document(),
        score=0.8,
    )

    result = RetrievalResultV1(
        query=query,
        hits=(hit,),
    )

    assert len(result.hits) == 1
    assert result.hits[0].score == 0.8


def test_models_are_frozen():
    query = RetrievalQueryV1(text="Tehran")

    with pytest.raises(ValidationError):
        query.limit = 10


def test_protocol_declares_retrieve():
    assert "retrieve" in TravelKnowledgeRetriever.__dict__