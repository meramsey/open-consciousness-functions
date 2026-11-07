"""Cue previews are read-only views; canonical locale resources need no banners."""

import pytest
from ocf_tools import cue_headers
from ocf_tools.utils import OCFError
from test_cue_templates import fixture


@pytest.mark.unit
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_header_splitter_preserves_authored_bytes(newline):
    body = "# Author's note\ntext: |\n  Keep  whitespace.\n".replace("\n", newline)
    prefix = (cue_headers.START + "# cue: 雲\n" + cue_headers.END).replace("\n", newline)
    assert cue_headers.split_header(prefix + body) == (prefix, body)
    assert cue_headers.split_header(body) == ("", body)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        cue_headers.END,
        cue_headers.START,
        "text: value\n" + cue_headers.START + cue_headers.END,
        cue_headers.START + "text: hidden-authority\n" + cue_headers.END,
        (cue_headers.START + cue_headers.END) * 2,
    ],
)
def test_malformed_or_non_comment_headers_fail_closed(text):
    with pytest.raises(OCFError):
        cue_headers.split_header(text)


@pytest.mark.unit
def test_preview_projects_current_function_cues_without_creating_an_authority(tmp_path):
    owner, _entry, catalog = fixture(tmp_path)
    text = cue_headers.header(owner, "en-US", catalog, tmp_path)
    assert '"symbol": "cue.primary"' in text
    assert '"spoken": "Plus Example"' in text
    assert cue_headers.header(owner, "en-US", catalog, tmp_path) == text
    assert cue_headers.plans(tmp_path) == {}
    assert cue_headers.draft_plans(tmp_path) == {}
    assert cue_headers.predecessor(tmp_path, "function.yaml", "current") == "current"


@pytest.mark.integration
def test_canonical_catalog_has_no_generated_cue_headers_or_snapshots():
    from ocf_tools.function_catalog import resources

    rows = resources(cue_headers.REPO_ROOT)
    assert len(rows) == 58
    assert all(
        not path.read_text(encoding="utf-8").startswith(cue_headers.START) for path, _ in rows
    )
    assert cue_headers.plans() == cue_headers.draft_plans() == {}
    assert cue_headers.check() == cue_headers.verify() == []


@pytest.mark.unit
def test_retired_writer_fails_without_touching_sources(tmp_path, monkeypatch):
    source = tmp_path / "function.yaml"
    source.write_text("canonical", encoding="utf-8")
    monkeypatch.setattr(cue_headers, "REPO_ROOT", tmp_path)
    with pytest.raises(OCFError, match="generation is retired"):
        cue_headers.main(["--write"])
    assert source.read_text(encoding="utf-8") == "canonical"
