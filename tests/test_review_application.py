"""Reviewed unknowns are accepted; missing questions and changed sources fail."""

import hashlib

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
