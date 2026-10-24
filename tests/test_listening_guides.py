"""Small isolated contracts plus current-registry and optional PDF integration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from ocf_tools import listening_guides as guides
from ocf_tools.commands import is_active, localized_cue
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog
from ocf_tools.models import FunctionRecord
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_synthetic_missing_and_draft_data_are_honest():
    record = FunctionRecord(
        "OCF-TST-001",
        "test",
        Path("test.yaml"),
        {
            "canonical": {"name": "Café & focus"},
            "lifecycle": {"activation": "manual", "persistence": "ongoing"},
        },
    )
    content = {
        "locale": "en-US",
        "primary": None,
        "secondary_commands": [],
        "purpose": "A draft purpose",
        "purpose_resolution": {"status": "draft"},
    }
    text = guides.function_markdown(record, content)
    assert "Purpose (draft): `A draft purpose`" in text
    assert "Description (not-supplied): Not supplied." in text
    assert "Primary cue: Not supplied." in text
    assert guides.MISSING in text
    assert "- Persistence: `ongoing`" in text
    assert "do not establish effects, duration" in text
    assert "Function-specific safety notes: Not supplied" in text


@pytest.mark.unit
def test_unreviewed_speech_is_not_published():
    record = FunctionRecord("OCF-TST-001", "test", Path("test.yaml"), {})
    content = {
        "locale": "en-US",
        "primary": {
            "command_id": "test",
            "display_cue": "PLUS-TEST",
            "spoken_cue": "Draft speech",
            "binding_status": "requires-locale-review",
        },
    }
    text = guides.function_markdown(record, content)
    assert "Display cue: `PLUS-TEST`" in text
    assert "Spoken cue: Not supplied as reviewed speech." in text
    assert "Draft speech" not in text


@pytest.mark.unit
def test_write_refuses_existing_and_checks_without_writing(tmp_path):
    docs = {"index.md": "# Test\n", "functions/test.md": "# Function\n"}
    assert guides.write_documents(docs, tmp_path, markdown_only=True) == 2
    before = (tmp_path / "index.md").stat().st_mtime_ns
    assert guides.write_documents(docs, tmp_path, markdown_only=True, check=True) == 2
    assert (tmp_path / "index.md").stat().st_mtime_ns == before
    with pytest.raises(OCFError, match="overwrite"):
        guides.write_documents(docs, tmp_path, markdown_only=True)
    (tmp_path / "index.md").write_text("changed", encoding="utf-8")
    with pytest.raises(OCFError, match="stale"):
        guides.write_documents(docs, tmp_path, markdown_only=True, check=True)
    assert (tmp_path / "index.md").read_text() == "changed"


@pytest.mark.unit
def test_collision_preflight_does_not_write_other_targets(tmp_path):
    (tmp_path / "second.md").write_text("private", encoding="utf-8")
    with pytest.raises(OCFError, match="overwrite"):
        guides.write_documents(
            {"first.md": "new", "second.md": "new"}, tmp_path, markdown_only=True
        )
    assert not (tmp_path / "first.md").exists()


@pytest.mark.unit
def test_missing_check_does_not_create_output(tmp_path):
    output = tmp_path / "missing"
    with pytest.raises(OCFError, match="missing or stale"):
        guides.write_documents({"index.md": "text"}, output, check=True, markdown_only=True)
    assert not output.exists()


@pytest.mark.unit
def test_inline_escapes_text_and_links_to_pdf():
    assert guides._inline("`Café <x> & y` [All](../index.md)") == (
        'Café &lt;x&gt; &amp; y <a href="../index.pdf">All</a>'
    )


@pytest.mark.unit
def test_html_is_offline_unicode_semantic_and_escapes_untrusted_text():
    text = guides.html_bytes(
        "# Café <unsafe>\n\n## Cues\n\n- `Plus Focus`\n- [All](../index.md)\n\n"
        "Text & safety. [Unsafe](javascript:alert)\n"
    ).decode("utf-8")
    assert '<meta charset="utf-8">' in text and "<main>" in text
    assert "<h1>Café &lt;unsafe&gt;</h1>" in text
    assert '<ul><li>Plus Focus</li><li><a href="../index.html">All</a></li></ul>' in text
    assert "Text &amp; safety." in text and "javascript:" not in text
    assert "<script" not in text


@pytest.mark.integration
def test_current_registry_all_58_guides_have_exact_active_cues():
    records = load_all_functions()
    assert len(records) == 58
    documents = guides.markdown_documents()
    assert len(documents) == 60
    assert (
        sum(line.startswith("## ") for line in documents["listening-guide.md"].splitlines()) == 20
    )
    catalog = LocaleCatalog()
    for record in records:
        text = documents[f"functions/{record.id}.md"]
        assert f"# {record.id}: {record.canonical_name}" in text
        assert guides.MISSING in text
        for command in record.command_records:
            if not is_active(command) or command.role == "legacy-alias":
                continue
            cue = localized_cue(record, command, catalog=catalog, strict=False)
            assert f"Display cue: {guides._literal(cue['display_cue'])}" in text
            if cue["binding_status"] == "resolved":
                assert f"Spoken cue: {guides._literal(cue['spoken_cue'])}" in text
    assert "Spoken cue: `Plus Focus`" in documents["functions/OCF-FND-002.md"]


@pytest.mark.integration
def test_pdf_deterministic_searchable_unicode_bookmarks_and_links(tmp_path):
    pytest.importorskip("reportlab")
    tool = shutil.which("pdftotext")
    if not tool:
        pytest.skip("pdftotext is not installed")
    source = "# Café listening\n\n## Cues\n\nSpoken cue: `Plus Focus`\n\n[All guides](index.md)\n"
    data = guides.pdf_bytes(source)
    assert data == guides.pdf_bytes(source)
    assert b"/Outlines" in data
    assert b"index.pdf" in data
    path = tmp_path / "guide.pdf"
    path.write_bytes(data)
    result = subprocess.run(
        [tool, str(path), "-"], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    assert "Café listening" in result.stdout
    assert "Spoken cue: Plus Focus" in result.stdout
    assert "1" in result.stdout


@pytest.mark.integration
def test_pdf_unsupported_glyph_fails_explicitly():
    pytest.importorskip("reportlab")
    with pytest.raises(OCFError, match="lacks glyphs"):
        guides.pdf_bytes("# Unsupported\n\n\U0001f9e0\n")


@pytest.mark.integration
def test_current_registry_pdf_and_markdown_freshness(tmp_path):
    pytest.importorskip("reportlab")
    documents = guides.markdown_documents()
    assert guides.write_documents(documents, tmp_path) == 180
    assert guides.write_documents(documents, tmp_path, check=True) == 180
    assert len(list(tmp_path.rglob("*.pdf"))) == 60
    assert len(list(tmp_path.rglob("*.html"))) == 60
