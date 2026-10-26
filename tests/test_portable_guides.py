import pytest
from ocf_tools import listening_guides
from ocf_tools.indexes import load_all_functions


@pytest.mark.integration
def test_portable_collection_is_self_contained_and_has_all_functions(tmp_path):
    package = tmp_path / "guides"
    result = listening_guides.build_portable_collection(package)
    assert result["functions"] == 58
    assert (package / "index.html").is_file()
    assert (package / "complete-guide.pdf").is_file()
    assert (package / "listening-guide.pdf").is_file()
    assert b"/Outlines" in (package / "complete-guide.pdf").read_bytes()
    for record in load_all_functions():
        for suffix in (".md", ".html", ".pdf"):
            assert (package / "functions" / f"{record.id}{suffix}").is_file()
    html = (package / "index.html").read_text(encoding="utf-8")
    assert "Search by title, ID, cue, or description" in html
    assert "https://" not in html and "http://" not in html


@pytest.mark.integration
def test_portable_collection_can_be_relocated_without_external_links(tmp_path):
    package = tmp_path / "guides"
    listening_guides.build_portable_collection(package)
    relocated = tmp_path / "copied" / "guides"
    import shutil

    shutil.copytree(package, relocated)
    for path in relocated.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "file:///" not in text
        assert "localhost" not in text
    assert (relocated / "complete-guide.pdf").is_file()
