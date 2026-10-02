from __future__ import annotations

from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


def _document(
    *,
    document_id: str,
    country_code: str = "IR",
    country_name: str = "Iran",
    region: str | None = "Tehran Province",
    city: str | None = "Tehran",
    category: str = "destination",
    title: str,
    summary: str,
    content: str,
    tags: tuple[str, ...] = (),
) -> TravelKnowledgeDocumentV1:
    return TravelKnowledgeDocumentV1(
        document_id=document_id,
        country_code=country_code,
        country_name=country_name,
        region=region,
        city=city,
        category=category,
        title=title,
        summary=summary,
        content=content,
        tags=tags,
        languages=("en",),
        sources=(),
    )


def test_empty_collection_returns_empty_hits():
    retriever = InMemoryTravelKnowledgeRetriever([])

    result = retriever.retrieve(
        RetrievalQueryV1(text="Tehran museums")
    )

    assert result.hits == ()


def test_title_match_ranks_above_content_only_match():
    title_match = _document(
        document_id="tehran.museum",
        title="Tehran Museum Guide",
        summary="A city guide.",
        content="Cultural attractions in Iran.",
    )

    content_match = _document(
        document_id="tehran.general",
        title="Tehran Travel Guide",
        summary="A city guide.",
        content="Includes museum recommendations.",
    )

    retriever = InMemoryTravelKnowledgeRetriever(
        [content_match, title_match]
    )

    result = retriever.retrieve(
        RetrievalQueryV1(text="museum")
    )

    assert result.hits[0].document.document_id == "tehran.museum"
    assert result.hits[0].score > result.hits[1].score


def test_tag_match_ranks_above_summary_match():
    tag_match = _document(
        document_id="tehran.food",
        title="Tehran Experiences",
        summary="Things to do.",
        content="Local activities.",
        tags=("bazaar",),
    )

    summary_match = _document(
        document_id="tehran.market",
        title="Tehran Guide",
        summary="Visit the bazaar.",
        content="Local activities.",
    )

    retriever = InMemoryTravelKnowledgeRetriever(
        [summary_match, tag_match]
    )

    result = retriever.retrieve(
        RetrievalQueryV1(text="bazaar")
    )

    assert result.hits[0].document.document_id == "tehran.food"


def test_zero_score_documents_are_excluded():
    document = _document(
        document_id="tehran.general",
        title="Tehran",
        summary="Iran capital.",
        content="Urban travel information.",
    )

    retriever = InMemoryTravelKnowledgeRetriever([document])

    result = retriever.retrieve(
        RetrievalQueryV1(text="skiing")
    )

    assert result.hits == ()


def test_limit_is_respected():
    documents = [
        _document(
            document_id=f"doc.{index}",
            title=f"Tehran Guide {index}",
            summary="Tehran travel.",
            content="Tehran information.",
        )
        for index in range(5)
    ]

    retriever = InMemoryTravelKnowledgeRetriever(documents)

    result = retriever.retrieve(
        RetrievalQueryV1(
            text="Tehran",
            limit=2,
        )
    )

    assert len(result.hits) == 2


def test_country_filter():
    iran = _document(
        document_id="iran.tehran",
        country_code="IR",
        country_name="Iran",
        title="Tehran",
        summary="Capital city.",
        content="Travel Tehran.",
    )

    france = _document(
        document_id="france.paris",
        country_code="FR",
        country_name="France",
        region="Ile-de-France",
        city="Paris",
        title="Paris",
        summary="Capital city.",
        content="Travel Tehran comparison.",
    )

    retriever = InMemoryTravelKnowledgeRetriever([iran, france])

    result = retriever.retrieve(
        RetrievalQueryV1(
            text="Tehran",
            country_code="IR",
        )
    )

    assert [hit.document.document_id for hit in result.hits] == [
        "iran.tehran"
    ]


def test_city_filter_is_case_insensitive():
    document = _document(
        document_id="tehran.city",
        city="Tehran",
        title="Tehran",
        summary="Capital.",
        content="Tehran travel.",
    )

    retriever = InMemoryTravelKnowledgeRetriever([document])

    result = retriever.retrieve(
        RetrievalQueryV1(
            text="Tehran",
            city="tehran",
        )
    )

    assert len(result.hits) == 1


def test_category_filter():
    destination = _document(
        document_id="tehran.destination",
        category="destination",
        title="Tehran",
        summary="City guide.",
        content="Tehran travel.",
    )

    culture = _document(
        document_id="tehran.culture",
        category="culture",
        title="Tehran Culture",
        summary="Culture guide.",
        content="Tehran culture.",
    )

    retriever = InMemoryTravelKnowledgeRetriever(
        [destination, culture]
    )

    result = retriever.retrieve(
        RetrievalQueryV1(
            text="Tehran",
            category="culture",
        )
    )

    assert [hit.document.document_id for hit in result.hits] == [
        "tehran.culture"
    ]


def test_equal_scores_are_ordered_by_document_id():
    first = _document(
        document_id="a.document",
        title="Tehran",
        summary="Travel.",
        content="Guide.",
    )

    second = _document(
        document_id="b.document",
        title="Tehran",
        summary="Travel.",
        content="Guide.",
    )

    retriever = InMemoryTravelKnowledgeRetriever(
        [second, first]
    )

    result = retriever.retrieve(
        RetrievalQueryV1(text="Tehran")
    )

    assert [hit.document.document_id for hit in result.hits] == [
        "a.document",
        "b.document",
    ]