"""Contract and integration tests for the first source-attributed QA slice."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.assistant.grounded_qa import TravelQuestionV1, answer_travel_question
from app.knowledge.contract import TravelKnowledgeDocumentV1, TravelKnowledgeSourceV1
from app.knowledge.loader import load_travel_knowledge_markdown
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


def _document(**overrides):
    data = dict(
        document_id="ir.tehran.sample",
        country_code="IR",
        country_name="Iran",
        city="Tehran",
        category="destination",
        title="Tehran Museums",
        summary="Tehran has several museums and cultural attractions.",
        content="Museums and cultural attractions around Tehran.",
    )
    data.update(overrides)
    return TravelKnowledgeDocumentV1(**data)


def test_answer_includes_document_ids_and_is_provisional():
    doc = _document(
        sources=(
            TravelKnowledgeSourceV1(
                title="Local guide", url="https://example.org/tehran"
            ),
        )
    )
    answer = answer_travel_question(
        TravelQuestionV1(question="Tehran museums", country_code="IR"),
        InMemoryTravelKnowledgeRetriever([doc]),
    )
    assert answer.status == "provisional"
    assert "[ir.tehran.sample]" in answer.answer
    assert "Verify current" in answer.answer
    assert answer.evidence[0].external_urls == ("https://example.org/tehran",)
    assert answer.needs_verification is True


def test_no_relevant_evidence_does_not_hallucinate():
    answer = answer_travel_question(
        TravelQuestionV1(question="Shiraz beaches"),
        InMemoryTravelKnowledgeRetriever([_document()]),
    )
    assert answer.status == "insufficient_evidence"
    assert answer.evidence == ()


def test_city_filter_prevents_cross_city_answers():
    answer = answer_travel_question(
        TravelQuestionV1(question="Tehran museums", city="Shiraz"),
        InMemoryTravelKnowledgeRetriever([_document()]),
    )
    assert answer.status == "insufficient_evidence"


def test_missing_external_sources_are_explicitly_provisional():
    answer = answer_travel_question(
        TravelQuestionV1(question="Tehran museums"),
        InMemoryTravelKnowledgeRetriever([_document()]),
    )
    assert answer.status == "provisional"
    assert answer.evidence[0].external_urls == ()
    assert answer.needs_verification is True


def test_only_https_external_urls_are_exposed():
    doc = _document(
        sources=(
            TravelKnowledgeSourceV1(
                title="Unsafe source", url="javascript:alert(1)"
            ),
        )
    )
    answer = answer_travel_question(
        TravelQuestionV1(question="Tehran museums"),
        InMemoryTravelKnowledgeRetriever([doc]),
    )
    assert answer.evidence[0].external_urls == ()


def test_input_contract_rejects_unbounded_or_malformed_values():
    for bad in [
        {"question": "x"},
        {"question": "Tehran museums", "max_results": 99},
        {"question": "Tehran museums", "country_code": "../../"},
    ]:
        with pytest.raises(ValidationError):
            TravelQuestionV1(**bad)


def test_real_knowledge_file_end_to_end():
    doc = load_travel_knowledge_markdown(
        Path("knowledge/iran/destinations/tehran.md")
    )
    answer = answer_travel_question(
        TravelQuestionV1(question="Tehran museums culture", city="Tehran"),
        InMemoryTravelKnowledgeRetriever([doc]),
    )
    assert answer.status == "provisional"
    assert answer.evidence[0].document_id == "ir.tehran.destination"
    assert answer.evidence[0].last_reviewed_at is not None
