"""Immutable local preservation, including recovery from repeated execution."""

import pytest
from tools import preserve_auditions
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


def test_file_source_and_source_mutation_during_copy_fail_closed(tmp_path, monkeypatch):
    source = tmp_path / "single.wav"
    source.write_bytes(b"original")
    output = tmp_path / "preserved"
    result = preserve(source, output)
    assert result["files"] == [
        {"file": source.name, "sha256": fingerprint(source), "bytes": len(b"original")}
    ]

    (output / source.name).unlink()
    original_copy = preserve_auditions.shutil.copy2

    def mutate_while_copying(origin, target):
        original_copy(origin, target)
        Path(origin).write_bytes(b"changed during preservation")

    from pathlib import Path

    monkeypatch.setattr(preserve_auditions.shutil, "copy2", mutate_while_copying)
    with pytest.raises(ValueError, match="source/copy identity changed"):
        preserve(source, output)


def test_preservation_cli_writes_verification_manifest(tmp_path, monkeypatch, capsys):
    import json
    import runpy
    import sys

    source = tmp_path / "source.wav"
    source.write_bytes(b"source bytes")
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        ["preserve_auditions", str(source), str(output)],
    )
    preserve_auditions.main()
    manifest = json.loads((output / "preservation-source.wav.json").read_text())
    assert manifest["files"][0]["sha256"] == fingerprint(source)
    assert "Verified 1 preserved artifact" in capsys.readouterr().out
    runpy.run_path(str(preserve_auditions.Path(preserve_auditions.__file__)), run_name="__main__")
    assert "Verified 1 preserved artifact" in capsys.readouterr().out


def test_output_equal_to_source_is_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="outside the source directory"):
        preserve(source, source)
