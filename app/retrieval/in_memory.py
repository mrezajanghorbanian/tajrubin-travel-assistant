from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.curated_aliases import CURATED_TRAVEL_TERMS
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
        *,
        bilingual_aliases: bool = False,
    ) -> None:
        self._documents = tuple(documents)
        self._bilingual_aliases = bilingual_aliases

    def retrieve(
        self,
        query: RetrievalQueryV1,
    ) -> RetrievalResultV1:
        candidates = tuple(
            document
            for document in self._documents
            if _matches_filters(document, query)
        )

        query_tokens = _query_tokens(query.text, city=query.city)
        if self._bilingual_aliases:
            query_tokens = _map_bilingual_terms(query_tokens)
            if query.city is not None:
                city_tokens = _map_bilingual_terms(_tokenize(query.city))
                without_city = query_tokens - city_tokens
                if without_city:
                    query_tokens = without_city

        scored = [
            (
                _score_document(
                    document=document,
                    query_tokens=query_tokens,
                    bilingual_aliases=self._bilingual_aliases,
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
    bilingual_aliases: bool = False,
) -> float:
    if not query_tokens:
        return 0.0

    tokenize = (lambda value: _map_bilingual_terms(_tokenize(value))) if bilingual_aliases else _tokenize
    title_tokens = tokenize(document.title)
    summary_tokens = tokenize(document.summary)
    content_tokens = tokenize(document.content)
    tag_tokens = frozenset(
        token
        for tag in document.tags
        for token in tokenize(tag)
    )

    title_overlap = len(query_tokens & title_tokens)
    summary_overlap = len(query_tokens & summary_tokens)
    content_overlap = len(query_tokens & content_tokens)
    tag_overlap = len(query_tokens & tag_tokens)

    # Do not present a partially matching document as evidence for an
    # unsupported qualifier (e.g. "museum opening hours" when only museum
    # information is available). Lexical AND is intentionally conservative.
    known_tokens = title_tokens | summary_tokens | content_tokens | tag_tokens
    if not query_tokens.issubset(known_tokens):
        return 0.0

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


_ARABIC_PERSIAN_CHARS = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})


def _canonical_text(value: str) -> str:
    """Normalize Arabic/Persian letter and numeric variants for retrieval.

    Treat half-spaces as word boundaries. This is not morphological
    stemming, semantic retrieval or a Farsi grammar model.
    """
    normalized = unicodedata.normalize("NFKC", value).translate(
        _ARABIC_PERSIAN_CHARS
    )
    normalized = normalized.replace("\u200c", " ").replace("\u200d", " ")
    normalized = normalized.replace("\u0640", "")
    normalized = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return normalized.casefold()


_QUERY_STOPWORDS = frozenset({
    "a", "an", "the", "in", "at", "on", "to", "for", "of",
    "and", "about", "please", "find", "show", "me", "my", "our",
    "where", "are", "can", "i", "is", "what", "which",
    "در", "به", "از", "برای", "با", "و", "را", "رو", "مورد",
    "های", "ها",
})


def _query_tokens(value: str, *, city: str | None) -> frozenset[str]:
    """Preserve only content terms; a city filter already constrains place.

    A city-only query must still be able to retrieve city documents.
    """
    tokens = _tokenize(value) - _QUERY_STOPWORDS
    if city is not None:
        remaining = tokens - _tokenize(city)
        if remaining:
            return remaining
    return tokens


def _map_bilingual_terms(tokens: frozenset[str]) -> frozenset[str]:
    return frozenset(CURATED_TRAVEL_TERMS.get(token, token) for token in tokens)


def _simple_english_plural(token: str) -> str:
    """Only conservative plural normalization; never invent synonyms.

    Applied to both queries and document fields so scoring stays symmetric.
    """
    if token.isascii() and token.isalpha():
        if len(token) >= 6 and token.endswith("ies"):
            return token[:-3] + "y"
        if len(token) >= 5 and token.endswith("s") and not token.endswith(
            ("ss", "us", "is")
        ):
            return token[:-1]
    return token


def _tokenize(value: str) -> frozenset[str]:
    return frozenset(
        _simple_english_plural(token)
        for token in _TOKEN_PATTERN.findall(_canonical_text(value))
        if token
    )


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(_canonical_text(value).split())


__all__ = [
    "InMemoryTravelKnowledgeRetriever",
]
