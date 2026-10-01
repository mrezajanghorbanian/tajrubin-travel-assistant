from __future__ import annotations

from pathlib import Path

import pytest

from app.knowledge.loader import (
    TravelKnowledgeLoadError,
    load_travel_knowledge_markdown,
)


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "document.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_loader_loads_real_tehran_document():
    path = Path(
        "knowledge/iran/destinations/tehran.md"
    )

    document = load_travel_knowledge_markdown(path)

    assert document.document_id == "ir.tehran.destination"
    assert document.country_code == "IR"
    assert document.country_name == "Iran"
    assert document.city == "Tehran"
    assert document.category == "destination"
    assert document.title == "Tehran"
    assert document.content


def test_loader_rejects_missing_front_matter(tmp_path):
    path = _write(
        tmp_path,
        "Tehran travel content without front matter.",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "missing_front_matter"


def test_loader_rejects_unterminated_front_matter(tmp_path):
    path = _write(
        tmp_path,
        "---\ndocument_id: ir.test\n",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "unterminated_front_matter"


def test_loader_rejects_empty_front_matter(tmp_path):
    path = _write(
        tmp_path,
        "---\n---\nContent",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "empty_front_matter"


def test_loader_rejects_invalid_yaml(tmp_path):
    path = _write(
        tmp_path,
        "---\ninvalid: [yaml\n---\nContent",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "invalid_front_matter"


def test_loader_rejects_non_mapping_front_matter(tmp_path):
    path = _write(
        tmp_path,
        "---\n- one\n- two\n---\nContent",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "invalid_front_matter"


def test_loader_rejects_empty_body(tmp_path):
    path = _write(
        tmp_path,
        """---
document_id: ir.test
country_code: IR
country_name: Iran
category: destination
title: Test
summary: Test summary
languages:
  - en
---
""",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "empty_content"


def test_loader_rejects_document_that_violates_contract(tmp_path):
    path = _write(
        tmp_path,
        """---
document_id: INVALID ID
country_code: IR
country_name: Iran
category: destination
title: Test
summary: Test summary
languages:
  - en
---
Valid body.
""",
    )

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(path)

    assert exc.value.code == "contract_rejected"


def test_loader_handles_utf8_bom(tmp_path):
    path = _write(
        tmp_path,
        """\ufeff---
document_id: ir.test.destination
country_code: IR
country_name: Iran
category: destination
title: Test Destination
summary: Test summary
languages:
  - en
---
Valid body.
""",
    )

    document = load_travel_knowledge_markdown(path)

    assert document.document_id == "ir.test.destination"


def test_loader_reports_unreadable_source(tmp_path):
    missing = tmp_path / "missing.md"

    with pytest.raises(TravelKnowledgeLoadError) as exc:
        load_travel_knowledge_markdown(missing)

    assert exc.value.code == "source_unreadable"