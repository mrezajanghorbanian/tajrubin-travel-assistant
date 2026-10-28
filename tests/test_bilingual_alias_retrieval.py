"""Opt-in bilingual retrieval probe, against unchanged lexical default."""
from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


def document(i, title, city="Tehran"):
    return TravelKnowledgeDocumentV1(
        document_id=i,country_code="IR",country_name="Iran",city=city,
        category="destination",title=title,summary="travel guide",
        content="general information",sources=(),
    )


DOCS=(
    document("museum","Tehran museum"),
    document("garden","Tehran garden"),
    document("desert","Yazd desert",city="Yazd"),
    document("food","Tehran food"),
    document("history","Shiraz history",city="Shiraz"),
)
CASES=(
    ("موزه","Tehran","museum"),
    ("باغ","Tehran","garden"),
    ("غذا","Tehran","food"),
    ("کویر","Yazd","desert"),
    ("تاریخ","Shiraz","history"),
    ("موزه در تهران","Tehran","museum"),
    ("باغ در تهران","Tehran","garden"),
)
NEGATIVE=(("ساعت بازدید موزه","Tehran"),("هزینه بلیت باغ","Tehran"),
          ("موزه","Yazd"),("پزشک","Tehran"))


def retrieve(text,city,enabled):
    return InMemoryTravelKnowledgeRetriever(DOCS,bilingual_aliases=enabled).retrieve(
        RetrievalQueryV1(text=text,city=city,limit=3)
    ).hits


def test_opt_in_bilingual_equivalence_recovers_exact_translations():
    gained=0
    for text,city,expected in CASES:
        baseline=retrieve(text,city,False)
        enhanced=retrieve(text,city,True)
        assert enhanced[0].document.document_id==expected
        if not baseline:
            gained+=1
    assert gained>=5


def test_bilingual_aliases_do_not_invent_unsupported_qualifiers():
    for text,city in NEGATIVE:
        assert retrieve(text,city,True)==()


def test_default_retrieval_behavior_remains_unmodified():
    assert retrieve("موزه","Tehran",False)==()
    assert retrieve("museum","Tehran",False)[0].document.document_id=="museum"


def test_bilingual_query_does_not_leak_across_cities():
    assert retrieve("موزه","Yazd",True)==()
