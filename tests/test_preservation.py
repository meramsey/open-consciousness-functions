"""Immutable local preservation, including recovery from repeated execution."""

import pytest
from tools.preserve_auditions import fingerprint, preserve


def test_preservation_is_idempotent_and_never_overwrites_different_bytes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "artifact.wav"
    original.write_bytes(b"audition identity")
    output = tmp_path / "preserved"
    first = preserve(source, output)
    assert preserve(source, output) == first
    assert first["files"][0]["sha256"] == fingerprint(original)
    (output / "artifact.wav").write_bytes(b"user change")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        preserve(source, output)
    assert original.read_bytes() == b"audition identity"
    assert (output / "artifact.wav").read_bytes() == b"user change"


def test_invalid_destination_and_missing_source(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        preserve(tmp_path, tmp_path / "nested")
    with pytest.raises(ValueError, match="no audition"):
        preserve(tmp_path / "absent", tmp_path / "output")
