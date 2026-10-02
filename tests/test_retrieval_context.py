from __future__ import annotations

import pytest

from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.context import build_grounded_retrieval_context
from app.retrieval.contract import (
    RetrievalHitV1,
    RetrievalQueryV1,
    RetrievalResultV1,
)


def _document(
    *,
    document_id: str,
    title: str = "Tehran",
    summary: str = "Iran capital.",
    content: str = "Travel information about Tehran.",
) -> TravelKnowledgeDocumentV1:
    return TravelKnowledgeDocumentV1(
        document_id=document_id,
        country_code="IR",
        country_name="Iran",
        region="Tehran Province",
        city="Tehran",
        category="destination",
        title=title,
        summary=summary,
        content=content,
        tags=("culture",),
        languages=("en",),
        sources=(),
    )


def _result(
    *hits: RetrievalHitV1,
) -> RetrievalResultV1:
    return RetrievalResultV1(
        query=RetrievalQueryV1(text="Tehran museums"),
        hits=hits,
    )


def test_empty_result_builds_empty_context():
    context = build_grounded_retrieval_context(
        _result()
    )

    assert context.query == "Tehran museums"
    assert context.items == ()
    assert context.rendered_text == ""


def test_context_preserves_document_identity_and_score():
    hit = RetrievalHitV1(
        document=_document(
            document_id="tehran.museum",
            title="Tehran Museum Guide",
        ),
        score=0.875,
    )

    context = build_grounded_retrieval_context(
        _result(hit)
    )

    assert len(context.items) == 1
    assert context.items[0].document_id == "tehran.museum"
    assert context.items[0].score == 0.875
    assert "document_id=tehran.museum" in context.rendered_text
    assert "score=0.8750" in context.rendered_text


def test_context_contains_title_summary_and_content():
    hit = RetrievalHitV1(
        document=_document(
            document_id="tehran.context",
            title="Tehran Museums",
            summary="Museum overview.",
            content="Includes national and contemporary art museums.",
        ),
        score=0.9,
    )

    context = build_grounded_retrieval_context(
        _result(hit)
    )

    text = context.items[0].text

    assert "Tehran Museums" in text
    assert "Museum overview." in text
    assert "Includes national and contemporary art museums." in text


def test_max_items_is_respected():
    hits = tuple(
        RetrievalHitV1(
            document=_document(
                document_id=f"doc.{index}"
            ),
            score=0.8,
        )
        for index in range(5)
    )

    context = build_grounded_retrieval_context(
        _result(*hits),
        max_items=2,
    )

    assert len(context.items) == 2


def test_item_text_is_truncated():
    hit = RetrievalHitV1(
        document=_document(
            document_id="long.document",
            title="Tehran",
            summary="A" * 200,
            content="B" * 2000,
        ),
        score=0.7,
    )

    context = build_grounded_retrieval_context(
        _result(hit),
        max_item_chars=150,
        max_total_chars=1000,
    )

    assert len(context.items[0].text) <= 150



def test_total_budget_keeps_items_consistent_with_rendered_text():
    hits = tuple(
        RetrievalHitV1(
            document=_document(
                document_id=f"bounded.{index}",
                content="X" * 1000,
            ),
            score=0.8,
        )
        for index in range(3)
    )

    context = build_grounded_retrieval_context(
        _result(*hits),
        max_items=3,
        max_item_chars=300,
        max_total_chars=500,
    )

    assert len(context.rendered_text) <= 500

    for item in context.items:
        assert item.text in context.rendered_text
        assert f"document_id={item.document_id}" in context.rendered_text

def test_rendered_text_respects_total_limit():
    hits = tuple(
        RetrievalHitV1(
            document=_document(
                document_id=f"doc.{index}",
                content="X" * 1000,
            ),
            score=0.8,
        )
        for index in range(5)
    )

    context = build_grounded_retrieval_context(
        _result(*hits),
        max_items=5,
        max_item_chars=300,
        max_total_chars=500,
    )

    assert len(context.rendered_text) <= 500


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_items": 0}, "max_items"),
        ({"max_item_chars": 99}, "max_item_chars"),
        (
            {
                "max_item_chars": 500,
                "max_total_chars": 499,
            },
            "max_total_chars",
        ),
    ],
)
def test_invalid_limits_are_rejected(
    kwargs: dict[str, int],
    message: str,
):
    with pytest.raises(ValueError, match=message):
        build_grounded_retrieval_context(
            _result(),
            **kwargs,
        )
