"""Harness²-inspired independent retrieval quality probes, not Harness² runtime.

All document contents are synthetic; measured scores are deterministic and
must not be interpreted as real tourism retrieval quality.
"""
from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever
from app.retrieval.contract import RetrievalQueryV1


def document(doc_id, city, title, summary, content, tags=()):
    return TravelKnowledgeDocumentV1(
        document_id=doc_id, country_code="IR", country_name="Iran",
        city=city, category="destination", title=title, summary=summary,
        content=content, tags=tags, languages=("en",), sources=(),
    )


CORPUS=(
    document("iran.tehran.museums","Tehran","Tehran museums","Tehran art museums","Museum galleries Tehran art",("museum","culture")),
    document("iran.tehran.food","Tehran","Tehran food","Iranian restaurants in Tehran","Tehran food tasting bazaar",("food","cuisine")),
    document("iran.shiraz.gardens","Shiraz","Shiraz gardens","Gardens and green space","Shiraz garden walks",("garden","nature")),
    document("iran.shiraz.history","Shiraz","Shiraz heritage","Shiraz historical sites","History and architecture of Shiraz",("history","heritage")),
    document("iran.yazd.desert","Yazd","Yazd desert","Desert travel around Yazd","Yazd desert nature",("desert","outdoors")),
    document("iran.yazd.food","Yazd","Yazd cuisine","Traditional food in Yazd","Yazd food culture",("food","cuisine")),
)
# Held-out examples exercise rank, filter, abstention and no cross-city bleed.
CASES=(
    ("museum", "Tehran", "iran.tehran.museums"),
    ("cuisine", "Tehran", "iran.tehran.food"),
    ("gardens", "Shiraz", "iran.shiraz.gardens"),
    ("heritage", "Shiraz", "iran.shiraz.history"),
    ("desert", "Yazd", "iran.yazd.desert"),
    ("food", "Yazd", "iran.yazd.food"),
    ("outdoors", "Yazd", "iran.yazd.desert"),
    ("history", "Shiraz", "iran.shiraz.history"),
    ("nature", "Shiraz", "iran.shiraz.gardens"),
    ("art", "Tehran", "iran.tehran.museums"),
)
NEGATIVE=(
    ("spacecraft launch schedules","Tehran"),
    ("deep sea whales","Yazd"),
    ("ski resort opening times","Shiraz"),
    ("airline flight delay","Tehran"),
)


def probe_retrieval():
    retriever=InMemoryTravelKnowledgeRetriever(CORPUS)
    outcomes=[]
    for query,city,expected in CASES:
        hits=retriever.retrieve(RetrievalQueryV1(text=query,city=city,limit=3)).hits
        ids=[hit.document.document_id for hit in hits]
        outcomes.append({
            "query":query,"expected":expected,
            "top1":ids[0] if ids else None,
            "recall_at_3":expected in ids,
            "city_filter_safe":all(h.document.city==city for h in hits),
        })
    for query,city in NEGATIVE:
        hits=retriever.retrieve(RetrievalQueryV1(text=query,city=city,limit=3)).hits
        outcomes.append({
            "query":query,"expected":None,
            "top1":hits[0].document.document_id if hits else None,
            "recall_at_3":not hits,
            "city_filter_safe":all(h.document.city==city for h in hits),
        })
    positives=outcomes[:len(CASES)]
    negatives=outcomes[len(CASES):]
    return {
        "total":len(outcomes),
        "precision_at_1":sum(x["top1"]==x["expected"] for x in positives)/len(positives),
        "recall_at_3":sum(x["recall_at_3"] for x in positives)/len(positives),
        "negative_abstention":sum(x["top1"] is None for x in negatives)/len(negatives),
        "filter_compliance":sum(x["city_filter_safe"] for x in outcomes)/len(outcomes),
        "cases":outcomes,
    }


def test_retrieval_probe_no_regression():
    report=probe_retrieval()
    assert report["total"]==14
    assert report["precision_at_1"]==1.0,report["cases"]
    assert report["recall_at_3"]==1.0
    assert report["negative_abstention"]==1.0
    assert report["filter_compliance"]==1.0
