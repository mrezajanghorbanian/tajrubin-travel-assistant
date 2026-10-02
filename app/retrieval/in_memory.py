from __future__ import annotations

import re
from collections.abc import Iterable

from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import (
    RetrievalHitV1,
    RetrievalQueryV1,
    RetrievalResultV1,
)

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


class InMemoryTravelKnowledgeRetriever:
    """Deterministic lexical retriever for small local knowledge collections."""

    def __init__(
        self,
        documents: Iterable[TravelKnowledgeDocumentV1],
    ) -> None:
        self._documents = tuple(documents)

    def retrieve(
        self,
        query: RetrievalQueryV1,
    ) -> RetrievalResultV1:
        candidates = tuple(
            document
            for document in self._documents
            if _matches_filters(document, query)
        )

        query_tokens = _tokenize(query.text)

        scored = [
            (
                _score_document(
                    document=document,
                    query_tokens=query_tokens,
                ),
                document,
            )
            for document in candidates
        ]

        ranked = sorted(
            scored,
            key=lambda item: (
                -item[0],
                item[1].document_id,
            ),
        )

        hits = tuple(
            RetrievalHitV1(
                document=document,
                score=score,
            )
            for score, document in ranked[: query.limit]
            if score > 0.0
        )

        return RetrievalResultV1(
            query=query,
            hits=hits,
        )


def _matches_filters(
    document: TravelKnowledgeDocumentV1,
    query: RetrievalQueryV1,
) -> bool:
    if (
        query.country_code is not None
        and document.country_code != query.country_code
    ):
        return False

    if (
        query.region is not None
        and _normalize(document.region) != _normalize(query.region)
    ):
        return False

    if (
        query.city is not None
        and _normalize(document.city) != _normalize(query.city)
    ):
        return False

    if (
        query.category is not None
        and document.category != query.category
    ):
        return False

    return True


def _score_document(
    *,
    document: TravelKnowledgeDocumentV1,
    query_tokens: frozenset[str],
) -> float:
    if not query_tokens:
        return 0.0

    title_tokens = _tokenize(document.title)
    summary_tokens = _tokenize(document.summary)
    content_tokens = _tokenize(document.content)
    tag_tokens = frozenset(
        token
        for tag in document.tags
        for token in _tokenize(tag)
    )

    title_overlap = len(query_tokens & title_tokens)
    summary_overlap = len(query_tokens & summary_tokens)
    content_overlap = len(query_tokens & content_tokens)
    tag_overlap = len(query_tokens & tag_tokens)

    weighted_matches = (
        title_overlap * 4
        + tag_overlap * 3
        + summary_overlap * 2
        + content_overlap
    )

    maximum_weight = len(query_tokens) * 10

    if maximum_weight == 0:
        return 0.0

    return min(
        weighted_matches / maximum_weight,
        1.0,
    )


def _tokenize(value: str) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in _TOKEN_PATTERN.findall(value)
        if token
    )


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None

    return " ".join(value.casefold().split())


__all__ = [
    "InMemoryTravelKnowledgeRetriever",
]