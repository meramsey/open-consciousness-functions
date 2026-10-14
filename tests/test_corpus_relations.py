"""Format equivalence is not independent historical evidence."""

import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools import corpus
from ocf_tools.utils import OCFError
from tools import analyze_corpus_relations
from tools.analyze_corpus_relations import analyze, content_hash


def test_format_equivalence_preserves_words_and_not_authenticated():
    assert content_hash("Hello world.", "txt") == content_hash(
        "1\n00:00:01,000 --> 00:00:02,000\nHello world.\n", "srt"
    )
    assert content_hash("Hello world.", "txt") != content_hash("Hello another world.", "txt")


def test_changed_source_is_not_silently_reclassified(tmp_path):
    path = tmp_path / "source.txt"
    path.write_bytes(b"Original words")
    row = {
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "function_id": "test",
        "source_type": "txt",
        "evidence_class": "unknown",
    }
    report = analyze(tmp_path, {"files": [row]})
    assert report["independently_authenticated_recordings"] == 0
    assert "Original words" not in str(report)
    path.write_bytes(b"Changed words")
    with pytest.raises(OCFError, match="changed since inventory"):
        analyze(tmp_path, {"files": [row]})


def test_analyze_text_binary_pdf_and_format_equivalence(monkeypatch, tmp_path):
    rows = []
    content = [
        ("first.txt", b"Function learning exercise.\nHello world."),
        (
            "second.srt",
            b"1\n00:00:01,000 --> 00:00:02,000\nFUNCTION LEARNING EXERCISE, HELLO WORLD!\n",
        ),
        ("opaque.bin", b"\x00\x01"),
        ("brochure.pdf", b"pdf bytes"),
    ]
    for name, data in content:
        (tmp_path / name).write_bytes(data)
        rows.append(
            {
                "path": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "function_id": "OCF-TST-001",
                "source_type": Path(name).suffix.lstrip("."),
                "evidence_class": "source_transcript" if name.endswith(".txt") else "unknown",
            }
        )

    monkeypatch.setattr(
        "tools.analyze_corpus_relations.shutil.which", lambda name: "/usr/bin/pdftotext"
    )
    monkeypatch.setattr(
        "tools.analyze_corpus_relations.workspace_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="Function Command\nPurpose: details\n",
            stderr="",
        ),
    )
    report = analyze(tmp_path, {"files": rows})
    by_path = {row["path"]: row for row in report["files"]}
    assert by_path["first.txt"]["candidate_categories"] == ["opener"]
    assert by_path["first.txt"]["word_count"] == 5
    assert by_path["brochure.pdf"]["evidence_class"] == "secondary_description"
    assert by_path["opaque.bin"]["inspection"] == "binary metadata only"
    assert report["content_equivalence_groups"][0]["representations"] == sorted(
        [rows[0]["sha256"], rows[1]["sha256"]]
    )
    assert report["independently_authenticated_recordings"] == 0


@pytest.mark.parametrize(
    "executable,returncode,inspection",
    [
        (None, 0, "binary metadata only"),
        ("pdftotext", 1, "PDF extraction failed; classification remains unknown"),
    ],
)
def test_pdf_extraction_unavailable_or_failed_stays_unclassified(
    monkeypatch, tmp_path, executable, returncode, inspection
):
    data = b"pdf"
    (tmp_path / "item.pdf").write_bytes(data)
    row = {
        "path": "item.pdf",
        "sha256": hashlib.sha256(data).hexdigest(),
        "function_id": None,
        "source_type": "pdf",
        "evidence_class": "unknown",
    }
    monkeypatch.setattr(
        "tools.analyze_corpus_relations.shutil.which",
        lambda _name: "/usr/bin/pdftotext" if executable else None,
    )
    monkeypatch.setattr(
        "tools.analyze_corpus_relations.workspace_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=returncode, stdout="", stderr="failure"
        ),
    )
    assert analyze(tmp_path, {"files": [row]})["files"][0]["inspection"] == inspection


def test_zip_members_are_hashed_in_memory_and_oversized_members_not_expanded(tmp_path):
    payload = b"Identical local words"
    (tmp_path / "local.txt").write_bytes(payload)
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("notes/readme.md", payload)
        archive.writestr("images/", b"")
        archive.writestr("images/photo.bin", b"binary")
        archive.writestr("oversized.txt", b"x" * (16 * 1024 * 1024 + 1))
    zip_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    local_row = {
        "path": "local.txt",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "function_id": None,
        "source_type": "txt",
        "evidence_class": "unknown",
    }
    zip_row = {
        "path": "bundle.zip",
        "sha256": zip_hash,
        "function_id": None,
        "source_type": "zip",
        "evidence_class": "unknown",
    }
    result = analyze(tmp_path, {"files": [local_row, zip_row]})["files"][1]
    regular, binary, oversized = result["members"]
    assert regular["name"] == "notes/readme.md"
    assert regular["equal_local_files"] == ["local.txt"]
    assert regular["evidence_class"] == "secondary_description"
    assert all(member["name"] != "images/" for member in result["members"])
    assert binary["evidence_class"] == "unknown"
    assert oversized == {"name": "oversized.txt", "inspection": "oversized member; not expanded"}
    assert "never extracted" in result["inspection"]


def test_corpus_inventory_and_matrix_keep_classification_uncertainty(monkeypatch, tmp_path):
    from types import SimpleNamespace

    root = tmp_path / "corpus"
    family = root / "+Transcripts From available tapes" / "Relax"
    family.mkdir(parents=True)
    (family / "Relax.txt").write_text(
        "Comfortable now.\n[missing]\nSay the command.\n", encoding="utf-8"
    )
    (family / "notes.md").write_text("Context, not a transcript.", encoding="utf-8")
    (family / "image.bin").write_bytes(b"\x00\x01")
    record = SimpleNamespace(
        id="OCF-FND-004",
        data={
            "legacy": {"name": "Relax", "source_availability": "available"},
            "canonical": {"name": "Relax", "command": {"primary": "PLUS-RELAX"}},
            "aliases": {"names": []},
        },
    )
    monkeypatch.setattr(corpus, "load_all_functions", lambda: [record])
    result = corpus.inventory(root)
    by_suffix = {Path(row["path"]).suffix: row for row in result["files"]}
    assert by_suffix[".txt"]["evidence_class"] == "partial_source_transcript"
    assert by_suffix[".txt"]["candidate_locators"]["preparation"] == [1]
    assert by_suffix[".md"]["evidence_class"] == "secondary_description"
    assert by_suffix[".bin"]["evidence_class"] == "unknown"
    assert by_suffix[".txt"]["related_files"] == [
        by_suffix[".bin"]["path"],
        by_suffix[".md"]["path"],
    ]
    function = result["functions"][0]
    assert function["function_id"] == "OCF-FND-004"
    assert function["source_derivative_available"] and not function["mockup_available"]
    rendered = corpus.markdown(result)
    assert "| OCF-FND-004 | Relax | yes | no | 3 | required |" in rendered
    assert "not independent audio authentication" in rendered


def test_corpus_inventory_requires_existing_root_and_classification_edges(tmp_path):
    with pytest.raises(OCFError, match="reference corpus not found"):
        corpus.inventory(tmp_path / "missing")
    assert corpus.classify(Path("random.bin"), None)[0] == "unknown"
    assert (
        corpus.classify(Path("mock.txt"), "Reconstructed transcript; not the original.")[0]
        == "reconstructed_mockup"
    )
    assert corpus.classify(Path("notes.md"), "Notes")[0] == "secondary_description"
    assert corpus.classify(Path("draft.txt"), "Ordinary prose")[0] == "unknown"
    assert corpus.candidate_locators(None) == {}


def test_corpus_relation_cli_writes_only_outside_read_only_root(monkeypatch, tmp_path, capsys):
    root = tmp_path / "reference"
    root.mkdir()
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"files": []}', encoding="utf-8")
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        analyze_corpus_relations.sys,
        "argv",
        [
            "analyze_corpus_relations",
            "--root",
            str(root),
            "--inventory",
            str(inventory),
            "--output",
            str(output),
        ],
    )
    analyze_corpus_relations.main()
    assert json.loads(output.read_text(encoding="utf-8"))["files"] == []
    assert json.loads(capsys.readouterr().out)["files"] == 0

    monkeypatch.setattr(
        analyze_corpus_relations.sys,
        "argv",
        [
            "analyze_corpus_relations",
            "--root",
            str(root),
            "--inventory",
            str(inventory),
            "--output",
            str(root / "report.json"),
        ],
    )
    with pytest.raises(OCFError, match="outside the read-only reference corpus"):
        analyze_corpus_relations.main()


def test_pdf_without_relevant_headings_remains_unknown(monkeypatch, tmp_path):
    data = b"pdf"
    (tmp_path / "item.pdf").write_bytes(data)
    row = {
        "path": "item.pdf",
        "sha256": hashlib.sha256(data).hexdigest(),
        "function_id": None,
        "source_type": "pdf",
        "evidence_class": "unknown",
    }
    monkeypatch.setattr(analyze_corpus_relations.shutil, "which", lambda _name: "pdftotext")
    monkeypatch.setattr(
        analyze_corpus_relations,
        "workspace_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="unrelated page", stderr=""),
    )
    result = analyze(tmp_path, {"files": [row]})["files"][0]
    assert result["heading_categories"] == []
    assert result["evidence_class"] == "unknown"


def test_corpus_relation_script_entrypoint_runs_main(monkeypatch, tmp_path, capsys):
    import runpy

    root = tmp_path / "reference"
    root.mkdir()
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"files": []}', encoding="utf-8")
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        analyze_corpus_relations.sys,
        "argv",
        [
            "analyze_corpus_relations.py",
            "--root",
            str(root),
            "--inventory",
            str(inventory),
            "--output",
            str(output),
        ],
    )
    runpy.run_path(str(Path(analyze_corpus_relations.__file__)), run_name="__main__")
    assert json.loads(output.read_text(encoding="utf-8"))["files"] == []
    assert json.loads(capsys.readouterr().out)["files"] == 0
