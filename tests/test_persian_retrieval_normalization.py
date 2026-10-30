"""Persian/Arabic lexical equivalence and negative-safety retrieval cases."""
from app.knowledge.contract import TravelKnowledgeDocumentV1
from app.retrieval.contract import RetrievalQueryV1
from app.retrieval.in_memory import InMemoryTravelKnowledgeRetriever


def doc(doc_id,title,city="تهران"):
    return TravelKnowledgeDocumentV1(
        document_id=doc_id,country_code="IR",country_name="Iran",
        city=city,category="destination",title=title,summary="راهنمای سفر",
        content="اطلاعات عمومی گردشگری",languages=("fa",),sources=(),
    )


def search(query,document,city=None):
    return InMemoryTravelKnowledgeRetriever([document]).retrieve(
        RetrievalQueryV1(text=query,city=city)
    ).hits


def test_arabic_yeh_and_kaf_match_persian_forms():
    assert search("كاشي",doc("ir.tile","کاشی"))[0].document.document_id=="ir.tile"


def test_half_space_and_regular_space_match():
    assert search("موزه های",doc("ir.museum","موزه‌های ایران"))


def test_persian_and_arabic_digits_match_ascii():
    assert search("۳",doc("ir.three","تالار 3"))
    assert search("٣",doc("ir.three","تالار 3"))


def test_diacritics_do_not_prevent_lexical_match():
    assert search("مُوزه",doc("ir.museum","موزه"))


def test_city_filter_normalizes_half_space_and_arabic_letters():
    document=doc("ir.city","مرکز فرهنگ",city="شهرک‌غرب")
    assert search("فرهنگ",document,city="شهرك غرب")


def test_unrelated_persian_question_still_abstains():
    assert search("ماهواره",doc("ir.museum","موزه‌های ایران"))==()


def test_different_city_is_not_returned():
    assert search("کاشی",doc("ir.tile","کاشی",city="اصفهان"),city="تهران")==()
