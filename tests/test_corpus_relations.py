"""Format equivalence is not independent historical evidence."""

import hashlib

import pytest
from ocf_tools.utils import OCFError
from tools.analyze_corpus_relations import analyze, content_hash


def test_format_equivalence_preserves_words_and_not_authenticated():
    assert content_hash("Hello world.", "txt") == content_hash("1\n00:00:01,000 --> 00:00:02,000\nHello world.\n", "srt")
    assert content_hash("Hello world.", "txt") != content_hash("Hello another world.", "txt")


def test_changed_source_is_not_silently_reclassified(tmp_path):
    path = tmp_path / "source.txt"
    path.write_bytes(b"Original words")
    row = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "function_id": "test", "source_type": "txt", "evidence_class": "unknown"}
    report = analyze(tmp_path, {"files": [row]})
    assert report["independently_authenticated_recordings"] == 0
    assert "Original words" not in str(report)
    path.write_bytes(b"Changed words")
    with pytest.raises(OCFError, match="changed since inventory"):
        analyze(tmp_path, {"files": [row]})
