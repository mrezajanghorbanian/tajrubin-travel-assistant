from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.knowledge.contract import (
    TravelKnowledgeDocumentV1,
    TravelKnowledgeSourceV1,
)


def _document(**overrides):
    data = {
        "document_id": "ir.tehran.golestan-palace",
        "country_code": "IR",
        "country_name": "Iran",
        "region": "Tehran Province",
        "city": "Tehran",
        "category": "attraction",
        "title": "Golestan Palace",
        "summary": "Historic royal complex in central Tehran.",
        "content": "Golestan Palace is a historic palace complex in Tehran.",
        "tags": ("history", "architecture", "unesco"),
        "languages": ("en",),
        "sources": (
            TravelKnowledgeSourceV1(
                title="Official source",
                url="https://example.com/golestan",
                publisher="Example Publisher",
                accessed_at=date(2026, 10, 1),
            ),
        ),
        "last_reviewed_at": date(2026, 10, 1),
    }
    data.update(overrides)
    return TravelKnowledgeDocumentV1(**data)


def test_travel_knowledge_document_accepts_valid_document():
    document = _document()

    assert document.knowledge_version == "1.0"
    assert document.document_id == "ir.tehran.golestan-palace"
    assert document.country_code == "IR"
    assert document.category == "attraction"
    assert document.city == "Tehran"
    assert document.tags == ("history", "architecture", "unesco")


def test_document_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        _document(unknown_field="not-allowed")


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        "IR.Tehran.Golestan",
        "contains spaces",
        "-starts-with-dash",
    ],
)
def test_document_rejects_invalid_document_id(document_id):
    with pytest.raises(ValidationError):
        _document(document_id=document_id)


@pytest.mark.parametrize(
    "country_code",
    [
        "ir",
        "IRN",
        "I",
        "12",
    ],
)
def test_document_rejects_invalid_country_code(country_code):
    with pytest.raises(ValidationError):
        _document(country_code=country_code)


def test_document_rejects_unknown_category():
    with pytest.raises(ValidationError):
        _document(category="hotel")


def test_document_requires_content():
    with pytest.raises(ValidationError):
        _document(content="")


def test_document_requires_at_least_one_language():
    with pytest.raises(ValidationError):
        _document(languages=())


def test_models_are_frozen():
    document = _document()

    with pytest.raises(ValidationError):
        document.title = "Changed title"