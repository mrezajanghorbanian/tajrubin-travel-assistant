"""Small auditable bilingual *term-equivalence* lexicon for local retrieval.

These are bounded translations of explicitly stated travel terms, not a
semantic model, authoritative tourism data, or inferred factual evidence.
Adding broader concepts here requires offline false-positive regression tests.
"""

# Tokenization first normalizes Persian/Arabic characters and basic English
# plurals. Keep concepts intentionally narrow (do not map garden to park,
# museum to gallery, historic to old, or desert to unsafe live-conditions).
CURATED_TRAVEL_TERMS: dict[str, str] = {
    "museum": "concept_museum",
    "موزه": "concept_museum",
    "garden": "concept_garden",
    "باغ": "concept_garden",
    "desert": "concept_desert",
    "کویر": "concept_desert",
    "restaurant": "concept_restaurant",
    "رستوران": "concept_restaurant",
    "architecture": "concept_architecture",
    "معماری": "concept_architecture",
    "food": "concept_food",
    "غذا": "concept_food",
    "history": "concept_history",
    "تاریخ": "concept_history",
    "heritage": "concept_heritage",
    "میراث": "concept_heritage",
    "bazaar": "concept_bazaar",
    "بازار": "concept_bazaar",
    # Fixed transliterations of known Iranian destinations. Do not infer
    # locations not present in this deliberately small reviewed dictionary.
    "tehran": "city_tehran",
    "تهران": "city_tehran",
    "shiraz": "city_shiraz",
    "شیراز": "city_shiraz",
    "isfahan": "city_isfahan",
    "esfahan": "city_isfahan",
    "اصفهان": "city_isfahan",
    "yazd": "city_yazd",
    "یزد": "city_yazd",
    "kashan": "city_kashan",
    "کاشان": "city_kashan",
    "tabriz": "city_tabriz",
    "تبریز": "city_tabriz",
    "kerman": "city_kerman",
    "کرمان": "city_kerman",
    "qeshm": "city_qeshm",
    "gheshm": "city_qeshm",
    "قشم": "city_qeshm",
}

__all__ = ["CURATED_TRAVEL_TERMS"]
