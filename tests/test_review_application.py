"""Reviewed unknowns are accepted; missing questions and changed sources fail."""

import hashlib
from copy import deepcopy

import pytest
from ocf_tools.utils import OCFError
from test_content import layers
from tools import apply_function_reviews as tool


@pytest.mark.unit
def test_review_application_binds_hash_full_extent_and_retains_maturity(tmp_path, monkeypatch):
    content = b"one\ntwo\nthree\n"
    (tmp_path / "mockup.txt").write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    data = layers()
    data["evidence"]["sources"][0]["sha256"] = sha
    data["evidence"]["observations"][0]["source_sha256"] = sha
    monkeypatch.setattr(tool, "load_layers", lambda identity: data)
    notes = {
        key: "unknown"
        for key in tool.SECTIONS
        if key not in ("identity", "provenance", "safety_claims")
    }
    notes.update(
        source="mockup.txt",
        family="synthetic",
        inspected_lines=[1, 3],
        claims=["synthetic-unverified-claim"],
        locators={"association": [1, 3], "main": [1, 3]},
        uncertainties="No authenticated recording",
        main=["proposed-operation"],
    )
    result = tool.apply_review("OCF-FND-004", notes, tmp_path)
    assert result["specifications"]["extraction_status"] == "complete"
    assert (
        result["specifications"]["maturity"] == "draft"
        and result["specifications"]["human_review"] == "required"
    )
    assert result["specifications"]["analysis_review"]["sections"]["main"]["status"] == "inferred"
    assert result["specifications"]["blocks"]["closer"]["status"] == "unknown"
    with pytest.raises(OCFError, match="skipped required"):
        tool.apply_review("OCF-FND-004", {}, tmp_path)
    with pytest.raises(OCFError, match="extent mismatch"):
        tool.apply_review("OCF-FND-004", {**notes, "inspected_lines": [1, 2]}, tmp_path)
    (tmp_path / "mockup.txt").write_bytes(b"changed")
    with pytest.raises(OCFError, match="does not match"):
        tool.apply_review("OCF-FND-004", notes, tmp_path)


@pytest.mark.unit
def test_review_application_brochure_is_separate_secondary_evidence(tmp_path, monkeypatch):
    transcript = b"one\ntwo\nthree\n"
    brochure_bytes = b"brochure pages"
    (tmp_path / "mockup.txt").write_bytes(transcript)
    (tmp_path / "brochure.pdf").write_bytes(brochure_bytes)
    transcript_hash = hashlib.sha256(transcript).hexdigest()
    brochure_hash = hashlib.sha256(brochure_bytes).hexdigest()
    data = layers()
    data["evidence"]["sources"][0].update(sha256=transcript_hash, path="mockup.txt")
    data["evidence"]["sources"].append(
        {
            **data["evidence"]["sources"][0],
            "sha256": brochure_hash,
            "path": "brochure.pdf",
            "evidence_class": "unknown",
        }
    )
    for observation in data["evidence"]["observations"]:
        observation["source_sha256"] = transcript_hash
    monkeypatch.setattr(tool, "load_layers", lambda _identity: deepcopy(data))
    notes = {
        key: "unknown"
        for key in tool.SECTIONS
        if key not in ("identity", "provenance", "safety_claims")
    }
    notes.update(
        source="mockup.txt",
        brochure="brochure.pdf",
        family="synthetic",
        inspected_lines=[1, 3],
        claims=["synthetic-claim"],
        locators={"association": [1, 3], "main": [1, 3]},
        uncertainties="No audio authentication",
        main=["documented-operation"],
    )
    result = tool.apply_review("OCF-FND-004", notes, tmp_path)
    evidence = result["evidence"]["sources"]
    assert (
        next(source for source in evidence if source["path"] == "brochure.pdf")["evidence_class"]
        == "secondary_description"
    )
    assert [
        locator["page"]
        for locator in result["specifications"]["analysis_review"]["sections"]["purpose"][
            "locators"
        ][1:]
    ] == [1, 2]
    assert result["specifications"]["blocks"]["main"]["operations"] == ["documented-operation"]

    notes["brochure"] = "missing.pdf"
    with pytest.raises(FileNotFoundError):
        tool.apply_review("OCF-FND-004", notes, tmp_path)

    (tmp_path / "unlisted.pdf").write_bytes(b"other brochure")
    notes["brochure"] = "unlisted.pdf"
    with pytest.raises(OCFError, match="does not match known evidence"):
        tool.apply_review("OCF-FND-004", notes, tmp_path)


@pytest.mark.unit
def test_review_application_reports_layer_validation_errors(tmp_path, monkeypatch):
    data = layers()
    transcript = b"one\ntwo\nthree\n"
    (tmp_path / "mockup.txt").write_bytes(transcript)
    data["evidence"]["sources"][0]["sha256"] = hashlib.sha256(transcript).hexdigest()
    monkeypatch.setattr(tool, "load_layers", lambda _identity: data)
    monkeypatch.setattr(tool, "validate_layers", lambda *_args: ["synthetic layer error"])
    notes = {
        key: "unknown"
        for key in tool.SECTIONS
        if key not in ("identity", "provenance", "safety_claims")
    }
    notes.update(
        source="mockup.txt",
        family="synthetic",
        inspected_lines=[1, 3],
        claims=[],
        locators={"association": [1, 3]},
        uncertainties="No audio authentication",
        main=["operation"],
    )
    with pytest.raises(OCFError, match="synthetic layer error"):
        tool.apply_review("OCF-FND-004", notes, tmp_path)


@pytest.mark.unit
def test_review_cli_merges_defaults_and_writes_only_when_apply_is_explicit(
    monkeypatch, tmp_path, capsys
):
    import sys

    notes = {
        "defaults": {"family": "default-family", "uncertainties": "default uncertainty"},
        "functions": {"OCF-FND-004": {"source": "notes.txt"}},
    }
    captured = []
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    monkeypatch.setattr(tool, "load_yaml_file", lambda _path: notes)
    monkeypatch.setattr(
        tool,
        "apply_review",
        lambda function_id, review, corpus: (
            captured.append((function_id, review, corpus))
            or {
                "evidence": {"function_id": function_id},
                "specifications": {"function_id": function_id},
            }
        ),
    )
    monkeypatch.setattr(
        sys, "argv", ["apply_function_reviews", "review.yaml", "--corpus", str(tmp_path)]
    )
    tool.main()
    assert captured[0][1]["family"] == "default-family"
    assert not (tmp_path / "function-content").exists()
    assert "1 functions" in capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        ["apply_function_reviews", "review.yaml", "--corpus", str(tmp_path), "--apply"],
    )
    tool.main()
    assert (tmp_path / "function-content/evidence/OCF-FND-004.yaml").is_file()
    assert (tmp_path / "function-content/specifications/OCF-FND-004.yaml").is_file()

    import runpy

    from ocf_tools import indexes

    monkeypatch.setattr(indexes, "load_yaml_file", lambda _path: {"functions": {}})
    monkeypatch.setattr(sys, "argv", ["apply_function_reviews", "empty.yaml"])
    runpy.run_path(str(tool.Path(tool.__file__)), run_name="__main__")
    assert "0 functions" in capsys.readouterr().out
