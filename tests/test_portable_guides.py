import re
import shutil
from io import BytesIO

import pytest
from ocf_tools import listening_guides
from ocf_tools.indexes import load_all_functions
from ocf_tools.utils import OCFError
from pypdf import PdfReader, PdfWriter


@pytest.fixture(scope="module")
def collection(tmp_path_factory):
    package = tmp_path_factory.mktemp("portable") / "guides"
    listening_guides.build_portable_collection(package)
    return package


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
def test_portable_collection_can_be_relocated_without_external_links(tmp_path, collection):
    relocated = tmp_path / "copied" / "guides"
    shutil.copytree(collection, relocated)
    for path in relocated.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "file:///" not in text
        assert "localhost" not in text
    assert (relocated / "complete-guide.pdf").is_file()
    result = listening_guides.validate_portable_collection(relocated)
    assert (result["files"], result["markdown"], result["html"], result["pdf"]) == (181, 60, 60, 61)
    assert result["broken_links"] == 0
    assert result["toc_entries"] > 58
    assert result["toc_links"] == 2 * result["toc_entries"]


@pytest.mark.integration
def test_category_indexes_share_canonical_order(collection):
    html = (collection / "index.html").read_text(encoding="utf-8")
    markdown = (collection / "index.md").read_text(encoding="utf-8")
    categories = sorted(
        {record.primary_domain or "Uncategorized" for record in load_all_functions()}
    )
    assert re.findall(r"<h2>(.*?)</h2>", html) == categories
    assert re.findall(r"^## (.*)$", markdown, re.MULTILINE) == categories
    html_ids = re.findall(r"<h3><a href='functions/(.*?)\.html'", html)
    markdown_ids = re.findall(r"\]\(functions/(.*?)\.md\)", markdown)
    assert html_ids == markdown_ids
    assert "&#x27;" in html


@pytest.mark.integration
def test_portable_zip_is_byte_stable(tmp_path):
    archives = []
    for number in range(2):
        archive = tmp_path / f"guides-{number}.zip"
        listening_guides.build_portable_collection(tmp_path / f"guides-{number}", zip_path=archive)
        archives.append(archive.read_bytes())
    assert archives[0] == archives[1]


@pytest.mark.integration
@pytest.mark.parametrize("corruption", ["directory", "missing", "asset", "escape"])
def test_relocation_validator_rejects_bad_links(tmp_path, collection, corruption):
    package = tmp_path / "guides"
    shutil.copytree(collection, package)
    if corruption == "directory":
        path = package / "index.md"
        path.write_text(
            re.sub(
                r"handbook p\. \d+", "handbook p. 9999", path.read_text(encoding="utf-8"), count=1
            ),
            encoding="utf-8",
        )
    elif corruption == "missing":
        (package / "functions/OCF-EXP-001.html").unlink()
    else:
        with (package / "index.html").open("a", encoding="utf-8") as stream:
            stream.write(
                '<img src="missing.png">'
                if corruption == "asset"
                else '<a href="../outside.md">escape</a>'
            )
    with pytest.raises(OCFError):
        listening_guides.validate_portable_collection(package)


@pytest.mark.integration
@pytest.mark.parametrize("corruption", ["wrong-guide", "dangling"])
def test_handbook_validator_rejects_wrong_toc_destination(collection, corruption):
    reader = PdfReader(collection / "complete-guide.pdf")
    writer = PdfWriter(clone_from=reader)
    annotation = writer.pages[1]["/Annots"][0].get_object()
    if corruption == "wrong-guide":
        annotation["/Dest"][0] = writer.pages[-1].indirect_reference
    else:
        from pypdf.generic import NameObject, TextStringObject

        annotation[NameObject("/Dest")] = TextStringObject("nonexistent")
    stream = BytesIO()
    writer.write(stream)
    directory = (collection / "index.md").read_text(encoding="utf-8")
    page_map = {
        identity: int(page)
        for identity, page in re.findall(
            r"`(OCF-[A-Z]+-\d+)` · \[Complete handbook p\. (\d+)", directory
        )
    }
    with pytest.raises(OCFError):
        listening_guides.validate_handbook(stream.getvalue(), load_all_functions(), page_map)
