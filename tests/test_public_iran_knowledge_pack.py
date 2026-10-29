"""Offline retrieval over the checked-in, publicly sourced Iran knowledge pack."""
from datetime import date
import json

import pytest

from app.assistant.demo import DEFAULT_KNOWLEDGE_ROOT, load_local_knowledge_pack, main
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


SOURCES = {
    'ir.tehran.golestan-palace': ('Tehran', 'attraction', 'https://whc.unesco.org/en/list/1422/'),
    'ir.isfahan.jame-mosque': ('Isfahan', 'attraction', 'https://whc.unesco.org/en/list/1397/'),
    'ir.yazd.historic-city': ('Yazd', 'destination', 'https://whc.unesco.org/en/list/1544/'),
}


@pytest.fixture(scope='module')
def documents():
    return load_local_knowledge_pack(DEFAULT_KNOWLEDGE_ROOT)


@pytest.mark.parametrize(('query', 'city', 'expected'), [
    ('Golestan Palace', 'Tehran', 'ir.tehran.golestan-palace'),
    ('کاخ گلستان در تهران', 'تهران', 'ir.tehran.golestan-palace'),
    ('Masjed-e Jame', 'Isfahan', 'ir.isfahan.jame-mosque'),
    ('Masjed-e Jāmé', 'Isfahan', 'ir.isfahan.jame-mosque'),
    ('مسجد جامع اصفهان', 'اصفهان', 'ir.isfahan.jame-mosque'),
    ('Historic City of Yazd', 'Yazd', 'ir.yazd.historic-city'),
    ('شهر تاریخی یزد', 'یزد', 'ir.yazd.historic-city'),
    ('معماری در یزد', 'Yazd', 'ir.yazd.historic-city'),
    ('architecture in Yazd', 'یزد', 'ir.yazd.historic-city'),
])
def test_sourced_pack_retrieves_exact_document_in_both_languages(documents, query, city, expected):
    result = InMemoryTravelKnowledgeRetriever(documents, bilingual_aliases=True).retrieve(
        RetrievalQueryV1(text=query, city=city, country_code='IR'),
    )
    assert [hit.document.document_id for hit in result.hits] == [expected]


@pytest.mark.parametrize(('query', 'filters'), [
    ('کاخ گلستان ساعت بازدید', {'city': 'تهران'}),
    ('Golestan Palace ticket prices', {'city': 'Tehran'}),
    ('مسجد جامع اصفهان رزرو', {'city': 'اصفهان'}),
    ('Yazd live weather', {'city': 'Yazd'}),
    ('کاخ گلستان', {'city': 'Shiraz'}),
    ('Golestan Palace', {'city': 'Tehran', 'country_code': 'GB'}),
    ('Masjed-e Jame', {'city': 'Yazd'}),
    ('historic city', {'city': 'Yazd', 'category': 'attraction'}),
])
def test_sourced_pack_does_not_supply_unknown_live_facts_or_wrong_places(documents, query, filters):
    result = InMemoryTravelKnowledgeRetriever(documents, bilingual_aliases=True).retrieve(
        RetrievalQueryV1(text=query, **filters),
    )
    assert result.hits == ()


@pytest.mark.parametrize('identifier', SOURCES)
def test_sourced_records_keep_review_and_publisher_provenance(documents, identifier):
    record = {item.document_id: item for item in documents}[identifier]
    city, category, url = SOURCES[identifier]
    assert record.city == city
    assert record.category == category
    assert set(record.languages) == {'en', 'fa'}
    assert record.last_reviewed_at == date(2026, 10, 29)
    assert len(record.sources) == 1
    assert record.sources[0].url == url
    assert record.sources[0].publisher == 'UNESCO World Heritage Centre'
    assert record.sources[0].accessed_at == record.last_reviewed_at


@pytest.mark.parametrize(('query', 'city', 'identifier'), [
    ('کاخ گلستان', 'تهران', 'ir.tehran.golestan-palace'),
    ('Masjed-e Jame', 'Isfahan', 'ir.isfahan.jame-mosque'),
    ('شهر تاریخی یزد', 'یزد', 'ir.yazd.historic-city'),
])
def test_demo_returns_official_source_url_and_provisional_status(capsys, query, city, identifier):
    assert main([query, '--city', city, '--country', 'IR', '--bilingual-aliases', '--format', 'json']) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer['status'] == 'provisional'
    assert answer['needs_verification'] is True
    assert [item['document_id'] for item in answer['evidence']] == [identifier]
    assert answer['evidence'][0]['external_urls'] == [SOURCES[identifier][2]]
    assert '[' + identifier + ']' in answer['answer']
