"""Offline CLI and knowledge-pack regression tests."""

import json
from pathlib import Path

import pytest

from app.assistant.demo import load_local_knowledge_pack, main


def _sample_document(document_id: str) -> str:
    return (
        "---\n"
        f"document_id: {document_id}\n"
        "country_code: IR\n"
        "country_name: Iran\n"
        "city: Tehran\n"
        "category: destination\n"
        "title: Tehran\n"
        "summary: Tehran is a cultural destination with museums.\n"
        "---\n"
        "Tehran has museums, galleries and historic buildings.\n"
    )


def test_text_demo_loads_real_knowledge(capsys):
    assert main(["Tehran museums", "--country", "IR", "--city", "Tehran"]) == 0
    output = capsys.readouterr().out
    assert "[ir.tehran.destination]" in output
    assert "Live prices" in output
    assert "Status: provisional" in output


def test_json_demo_is_parseable_and_attributed(capsys):
    assert main(["Tehran culture", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "provisional"
    assert output["evidence"][0]["document_id"] == "ir.tehran.destination"
    assert output["needs_verification"] is True


def test_no_match_returns_explicit_abstention(capsys):
    assert main(["astronaut orbital station", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "insufficient_evidence"
    assert output["evidence"] == []


def test_unknown_knowledge_pack_is_handled_without_traceback(tmp_path, capsys):
    assert main(["Tehran", "--knowledge-root", str(tmp_path / "missing")]) == 2
    assert "Knowledge root does not exist" in capsys.readouterr().err


def test_invalid_filter_exits_nonzero(capsys):
    assert main(["Tehran museums", "--country", "INVALID"]) == 2
    assert "Travel demo input error" in capsys.readouterr().err


def test_local_knowledge_pack_rejects_duplicates(tmp_path):
    (tmp_path / "a.md").write_text(_sample_document("ir.tehran.same"))
    (tmp_path / "b.md").write_text(_sample_document("ir.tehran.same"))
    with pytest.raises(ValueError, match="Duplicate knowledge"):
        load_local_knowledge_pack(tmp_path)


def test_local_knowledge_pack_rejects_oversized_collection(tmp_path):
    (tmp_path / "a.md").write_text(_sample_document("ir.tehran.a"))
    (tmp_path / "b.md").write_text(_sample_document("ir.tehran.b"))
    with pytest.raises(ValueError, match="document-count"):
        load_local_knowledge_pack(tmp_path, max_documents=1)


def test_local_knowledge_pack_rejects_symlink(tmp_path):
    source = tmp_path / "original.md"
    source.write_text(_sample_document("ir.tehran.original"))
    link = tmp_path / "linked.md"
    try:
        link.symlink_to(source)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks are not available")
    with pytest.raises(ValueError, match="symlinked"):
        load_local_knowledge_pack(tmp_path)


def test_local_knowledge_pack_rejects_empty_directory(tmp_path):
    with pytest.raises(ValueError, match="no Markdown"):
        load_local_knowledge_pack(tmp_path)
