import pytest

from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever
from tests.test_bilingual_alias_retrieval import document


@pytest.mark.parametrize(('stored_city', 'filter_city', 'query'), [
    ('Tehran', 'تهران', 'موزه در تهران'),
    ('تهران', 'Tehran', 'museum in Tehran'),
    ('Isfahan', 'اصفهان', 'museum'),
    ('اصفهان', 'Esfahan', 'موزه'),
    ('Qeshm', 'gheshm', 'museum'),
    ('شيراز', 'Shiraz', 'موزه'),
])
def test_opt_in_city_filter_matches_only_reviewed_equivalents(stored_city, filter_city, query):
    retriever = InMemoryTravelKnowledgeRetriever(
        (document('target', 'Museum موزه', city=stored_city),), bilingual_aliases=True,
    )
    hits = retriever.retrieve(RetrievalQueryV1(text=query, city=filter_city)).hits
    assert [hit.document.document_id for hit in hits] == ['target']


@pytest.mark.parametrize('city', ['یزد', 'Tehrann', 'Tehran province', 'museum', 'city_tehran'])
def test_opt_in_city_filter_does_not_fuzzily_expand(city):
    retriever = InMemoryTravelKnowledgeRetriever(
        (document('target', 'Tehran museum'),), bilingual_aliases=True,
    )
    assert retriever.retrieve(RetrievalQueryV1(text='موزه', city=city)).hits == ()


def test_default_city_filter_keeps_exact_normalized_matching():
    retriever = InMemoryTravelKnowledgeRetriever((document('target', 'Museum'),))
    assert retriever.retrieve(RetrievalQueryV1(text='museum', city='تهران')).hits == ()


@pytest.mark.parametrize('filters', [
    {'country_code': 'GB'}, {'region': 'Tehran'}, {'category': 'food'},
])
def test_bilingual_city_equivalence_does_not_bypass_other_filters(filters):
    retriever = InMemoryTravelKnowledgeRetriever(
        (document('target', 'Museum'),), bilingual_aliases=True,
    )
    assert retriever.retrieve(
        RetrievalQueryV1(text='موزه', city='تهران', **filters)
    ).hits == ()

