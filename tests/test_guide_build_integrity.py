"""Guide build metadata, extraction checks and edition preservation boundaries."""

import pytest
from ocf_tools.listening_guides import (
    build_portable_collection,
    guide_build_manifest,
    validate_extracted_narration,
)
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def test_reader_headings_preserve_section_bounds_while_allowing_page_footers():
    expected = {
        "fixture.opener": "Exact opening words.",
        "fixture.function-body": "Complete body words.",
        "fixture.closer": "Final words.",
    }
    text = "Introduction Exact opening words. Practice Complete body 12 words. Closing Final words."
    assert validate_extracted_narration(text, expected, markers=False) == 3
    with pytest.raises(OCFError, match="missing canonical narration text"):
        validate_extracted_narration(
            "Introduction Omitted. Practice Exact opening words. Complete body words. Closing Final words.",
            expected,
            markers=False,
        )
    with pytest.raises(OCFError, match="section heading"):
        validate_extracted_narration("Introduction Exact opening words.", expected, markers=False)


def test_pdf_resource_sections_allow_wrapping_but_not_missing_text_or_cross_section_matches():
    expected = {"fixture.opener": "Exact opening words.", "fixture.body": "Complete body words."}
    text = "fixture.opener Narration status reviewed Exact opening\n1\nwords. fixture.body Complete body words."
    assert validate_extracted_narration(text, expected) == 2
    with pytest.raises(OCFError, match="missing canonical narration text"):
        validate_extracted_narration(
            "fixture.opener Omitted. fixture.body Exact opening words. Complete body words.",
            expected,
        )
    with pytest.raises(OCFError, match="missing a canonical narration key"):
        validate_extracted_narration("fixture.opener Exact opening words.", expected)
    with pytest.raises(OCFError, match="ambiguous"):
        validate_extracted_narration(
            "fixture.body text", {"fixture.body": "text", "fixture-body": "text"}
        )


@pytest.mark.parametrize("edition,revision", [("unknown", None), ("0.5.0", "not-a-commit")])
def test_build_manifest_rejects_invalid_version_or_revision_before_loading_sources(
    edition, revision
):
    with pytest.raises(OCFError):
        guide_build_manifest([], edition, source_revision=revision)


def test_existing_guide_archive_is_never_overwritten(tmp_path):
    archive = tmp_path / "old-guides.zip"
    archive.write_bytes(b"preserve prior guide edition")
    with pytest.raises(OCFError, match="refusing to overwrite existing guide archive"):
        build_portable_collection(tmp_path / "new-guides", edition="0.5.0", zip_path=archive)
    assert archive.read_bytes() == b"preserve prior guide edition"
    assert not (tmp_path / "new-guides").exists()


def test_archive_cannot_include_itself_in_input_collection(tmp_path):
    with pytest.raises(OCFError, match="inside its input"):
        build_portable_collection(tmp_path / "guides", zip_path=tmp_path / "guides/archive.zip")


def test_existing_verified_guides_can_be_zipped_without_pdf_regeneration(tmp_path, monkeypatch):
    import zipfile

    from ocf_tools import listening_guides

    output = tmp_path / "guides"
    output.mkdir()
    (output / "index.md").write_text("Synthetic guide fixture", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        listening_guides, "validate_portable_collection", lambda path: calls.append(path)
    )
    archive = tmp_path / "guides.zip"
    listening_guides.write_guide_zip(output, archive)
    assert calls == [output.resolve()]
    with zipfile.ZipFile(archive) as reader:
        assert reader.read("index.md") == b"Synthetic guide fixture"
    before = archive.read_bytes()
    with pytest.raises(OCFError, match="overwrite"):
        listening_guides.write_guide_zip(output, archive)
    assert archive.read_bytes() == before
    with pytest.raises(OCFError, match="inside its input"):
        listening_guides.write_guide_zip(output, output / "nested.zip")
