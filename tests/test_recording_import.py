"""Directory imports require explicit identity, preserve bytes and bind the session."""

import hashlib
import json

import pytest
from ocf_tools.recordings import import_directory, prepare_recordings, unique_mapping
from ocf_tools.utils import OCFError
from test_recordings import package


def test_measured_directory_package_preserves_originals_and_rejects_wrong_session(tmp_path):
    doc, _, old = package(tmp_path)
    original = (tmp_path / "first.wav").read_bytes()
    result = import_directory(
        doc,
        tmp_path,
        {"first": "first.wav", "second": "second.wav"},
        tmp_path / "imported.yaml",
        locale="en-US",
        author="user",
        license="private",
    )
    assert result["recordings"]["second"]["measured_duration_s"] == 2
    assert result["recordings"]["first"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert (tmp_path / "first.wav").read_bytes() == original
    prepare_recordings(tmp_path / "imported.yaml", doc, "en-US")
    wrong = {**doc, "id": "different-session"}
    with pytest.raises(OCFError, match="different session"):
        prepare_recordings(tmp_path / "imported.yaml", wrong, "en-US")


def test_import_missing_unknown_duplicate_and_existing_outputs_are_diagnosed(tmp_path):
    doc, _, old = package(tmp_path)
    with pytest.raises(OCFError, match="missing"):
        import_directory(
            doc,
            tmp_path,
            {"first": "first.wav"},
            tmp_path / "imported.yaml",
            locale="en-US",
            author="user",
            license="private",
        )
    with pytest.raises(OCFError, match="duplicate"):
        json.loads('{"first":"a.wav","first":"b.wav"}', object_pairs_hook=unique_mapping)
    (tmp_path / "unknown.wav").write_bytes(b"unused")
    with pytest.raises(OCFError, match="unmapped audio"):
        import_directory(
            doc,
            tmp_path,
            {"first": "first.wav", "second": "second.wav"},
            tmp_path / "imported.yaml",
            locale="en-US",
            author="user",
            license="private",
        )
    assert not (tmp_path / "imported.yaml").exists()
