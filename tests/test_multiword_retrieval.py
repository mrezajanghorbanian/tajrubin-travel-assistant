"""Conservative multiword retrieval: relevance, word forms, and abstention."""
from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


def doc(identifier,title,summary,city="Tehran",content="Travel information",tags=()):
    return TravelKnowledgeDocumentV1(
        document_id=identifier,country_code="IR",country_name="Iran",
        city=city,category="destination",title=title,
        summary=summary,content=content,tags=tags,languages=("en",),sources=(),
    )


def hits(query,documents,city=None):
    return InMemoryTravelKnowledgeRetriever(documents).retrieve(
        RetrievalQueryV1(text=query,city=city)
    ).hits


def test_multiword_query_requires_all_content_terms():
    docs=(doc("d.food","Tehran food","Local cuisine"),
          doc("d.museum","Tehran museum","Modern art"))
    assert hits("food museum",docs,city="Tehran")==()


def test_relevant_multiword_document_ranks_ahead_of_partial_match():
    docs=(doc("d.partial","Tehran museums","Museum guide"),
          doc("d.full","Tehran museums and gardens","Museum and garden guide"))
    result=hits("museums gardens in Tehran",docs,city="Tehran")
    assert [item.document.document_id for item in result]==["d.full"]


def test_english_basic_plural_match_is_symmetric():
    assert hits("gardens", (doc("d.garden","Garden guide","Nature walks"),))


def test_multiword_persian_query_with_halfspaces():
    docs=(doc("d.good","موزه‌های تاریخی","هنر شهر",city="تهران"),
          doc("d.bad","موزه‌های طبیعی","گیاهان",city="تهران"))
    result=hits("موزه های تاریخی در تهران",docs,city="تهران")
    assert [item.document.document_id for item in result]==["d.good"]


def test_unknown_qualifier_does_not_return_weak_evidence():
    docs=(doc("d.museum","Tehran museum","Visitor guide"),)
    assert hits("museum opening hours",docs,city="Tehran")==()


def test_no_city_filter_still_uses_city_term_in_query():
    docs=(doc("d.tehran","Tehran museum","Art",city="Tehran"),
          doc("d.shiraz","Shiraz museum","Art",city="Shiraz"))
    result=hits("Tehran museum",docs)
    assert [item.document.document_id for item in result]==["d.tehran"]


def test_city_only_query_with_city_filter_still_works():
    docs=(doc("d.tehran","Tehran guide","Tehran attractions"),)
    assert hits("Tehran",docs,city="Tehran")


def test_existing_title_preference_remains():
    docs=(doc("d.title","Museum","Art"),
          doc("d.content","Cultural guide","Art",content="Museum collections"))
    result=hits("museum",docs)
    assert result[0].document.document_id=="d.title"
