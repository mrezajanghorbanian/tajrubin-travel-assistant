"""Catalog importer and persistence regression suite (synthetic records only)."""
import json
from datetime import date, time
import pytest

from app.knowledge.attraction_catalog import (
    AccessibilityV1, AttractionRecordV1, CatalogSourceV1,
    DatedOpeningV1, GeoPointV1,
)
from app.knowledge.catalog_import import CatalogImportError, load_catalog_json
from app.knowledge.catalog_repository import (
    CatalogRepositoryError, SQLiteAttractionRepository,
)


def record(name="sample.one", kind="editorial"):
    source = CatalogSourceV1(
        source_id="synthetic.source", title="Synthetic test document",
        kind=kind,
        url="https://example.org/fixture" if kind != "fixture" else None,
        observed_at=date(2026, 10, 1), valid_through=date(2026, 11, 30),
    )
    return AttractionRecordV1(
        attraction_id=name, knowledge_document_id=name + ".doc",
        name="Synthetic Gallery", country_code="IR", city="Tehran",
        location=GeoPointV1(latitude=35.1, longitude=51.1, source_id=source.source_id),
        visit_duration_minutes=60, duration_source_id=source.source_id,
        accessibility=AccessibilityV1(wheelchair_access="unknown"),
        opening_windows=(DatedOpeningV1(
            on_date=date(2026, 11, 3), opens_at=time(9), closes_at=time(17),
            source_id=source.source_id,
        ),),
        sources=(source,),
    )


def write_catalog(path, records):
    path.write_text(json.dumps({
        "catalog_version": "1.0",
        "records": [item.model_dump(mode="json") for item in records],
    }), encoding="utf-8")


def test_json_import_to_persistent_repo_roundtrip(tmp_path):
    input_file = tmp_path / "catalog.json"
    write_catalog(input_file, [record()])
    loaded = load_catalog_json(input_file)
    db = tmp_path / "catalog.db"
    with SQLiteAttractionRepository(db) as repo:
        assert repo.insert(loaded) == 1
        assert repo.count() == 1
        assert repo.get("sample.one") == record()
    with SQLiteAttractionRepository(db) as repo:
        assert repo.get("sample.one") == record()


def test_country_city_and_text_search(tmp_path):
    with SQLiteAttractionRepository(tmp_path / "c.db") as repo:
        repo.insert((record("sample.two"), record()))
        found = repo.search(country_code="IR", city="tehran", text="Gallery", limit=5)
        assert tuple(x.attraction_id for x in found) == ("sample.one", "sample.two")


def test_sql_injection_is_not_executable(tmp_path):
    with SQLiteAttractionRepository(tmp_path / "c.db") as repo:
        repo.insert((record(),))
        assert repo.search(text="' OR 1=1 --") == ()
        assert repo.count() == 1


def test_duplicate_insert_rolls_back_entire_batch(tmp_path):
    with SQLiteAttractionRepository(tmp_path / "c.db") as repo:
        repo.insert((record(),))
        with pytest.raises(CatalogRepositoryError, match="rolled back"):
            repo.insert((record("sample.other"), record()))
        assert repo.count() == 1
        assert repo.get("sample.other") is None


def test_duplicate_ids_in_one_batch_rejected(tmp_path):
    with SQLiteAttractionRepository(tmp_path / "c.db") as repo:
        with pytest.raises(CatalogRepositoryError, match="Duplicate"):
            repo.insert((record(), record()))
        assert repo.count() == 0


def test_fixture_cannot_import_by_default(tmp_path):
    with SQLiteAttractionRepository(tmp_path / "c.db") as repo:
        with pytest.raises(CatalogRepositoryError, match="fixture"):
            repo.insert((record(kind="fixture"),))
        assert repo.insert((record(kind="fixture"),), allow_synthetic_fixtures=True) == 1


def test_version_mismatch_rejected(tmp_path):
    p = tmp_path / "c.json"
    write_catalog(p, [])
    p.write_text(p.read_text().replace('"1.0"', '"2.0"'))
    with pytest.raises(CatalogImportError, match="version"):
        load_catalog_json(p)


def test_duplicate_json_keys_rejected(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"catalog_version":"1.0","records":[],"records":[]}')
    with pytest.raises(CatalogImportError, match="Duplicate JSON key"):
        load_catalog_json(p)


def test_duplicate_ids_rejected_at_import(tmp_path):
    p = tmp_path / "c.json"
    write_catalog(p, [record(), record()])
    with pytest.raises(CatalogImportError, match="Duplicate attraction"):
        load_catalog_json(p)


def test_oversized_file_rejected(tmp_path):
    p = tmp_path / "c.json"
    p.write_bytes(b"x" * 2_000_001)
    with pytest.raises(CatalogImportError, match="byte limit"):
        load_catalog_json(p)


def test_empty_catalog_round_trip(tmp_path):
    p = tmp_path / "c.json"
    write_catalog(p, [])
    assert load_catalog_json(p) == ()


@pytest.mark.parametrize("filters", [
    {"limit": 0}, {"limit": 51}, {"country_code": "ir"},
    {"city": ""}, {"text": ""},
])
def test_bad_search_filters_rejected(tmp_path, filters):
    with SQLiteAttractionRepository(tmp_path / "c.db") as repo:
        with pytest.raises(CatalogRepositoryError):
            repo.search(**filters)


def test_schema_rejects_unknown_attributes(tmp_path):
    p = tmp_path / "c.json"
    write_catalog(p, [record()])
    data = json.loads(p.read_text())
    data["records"][0]["untrusted_extra"] = "discard me"
    p.write_text(json.dumps(data))
    with pytest.raises(CatalogImportError, match="schema"):
        load_catalog_json(p)
