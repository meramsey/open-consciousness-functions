"""Meaningful failure-path coverage for atomic I/O, content identities and registry."""

from copy import deepcopy

import pytest
from ocf_tools import paths, utils
from ocf_tools.content import validate_layers
from ocf_tools.indexes import load_yaml_file
from ocf_tools.recordings import prepare_recordings
from ocf_tools.voice_registry import load_registry
from test_content import layers
from test_recordings import package


def test_atomic_failure_keeps_original_and_cleans_temp(tmp_path, monkeypatch):
    target = tmp_path / "config.yaml"
    target.write_text("original")
    with pytest.raises(utils.OCFFileExistsError):
        utils.write_text_atomic(target, "new", overwrite=False)

    def fail(fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(utils.os, "fsync", fail)
    with pytest.raises(OSError, match="fsync"):
        utils.write_text_atomic(target, "new")
    assert target.read_text() == "original"
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(utils.OCFError, match="not found"):
        utils.read_text(tmp_path / "absent")


def test_paths_only_discover_directories_and_metadata_does_not_guess(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "FUNCTIONS_DIR", tmp_path / "missing")
    assert paths.all_function_dirs() == []
    (tmp_path / "body").mkdir()
    (tmp_path / "note.txt").write_text("not a domain")
    monkeypatch.setattr(paths, "FUNCTIONS_DIR", tmp_path)
    assert paths.all_function_dirs() == [tmp_path / "body"]
    assert paths.domain_path("body") == tmp_path / "body"


def test_content_unknown_identity_source_duplicates_and_bad_bindings():
    data = layers()
    data["unknown-layer"] = {}
    assert any("unknown content layer" in error for error in validate_layers(data, "OCF-FND-004"))
    data = layers()
    assert any("identity mismatch" in error for error in validate_layers(data, "OCF-FND-002"))
    data = layers()
    data["evidence"]["observations"].append(deepcopy(data["evidence"]["observations"][0]))
    assert "duplicate observation identity" in validate_layers(data, "OCF-FND-004")
    data = layers()
    data["evidence"]["observations"][0]["source_sha256"] = "0" * 64
    assert "observation refers to unknown source fingerprint" in validate_layers(
        data, "OCF-FND-004"
    )
    data = layers()
    data["bindings"]["narration_resources"] = [{"locale": "unknown", "key": "unknown"}]
    assert "binding refers to an unavailable locale resource" in validate_layers(
        data, "OCF-FND-004"
    )


def test_registry_duplicate_and_invalid_terms_are_not_accepted(tmp_path):
    from conftest import REPO_ROOT

    record = load_yaml_file(REPO_ROOT / "templates/community-voice.yaml")
    utils.write_text_atomic(tmp_path / "one.yaml", utils.yaml_safe_dump(record))
    assert load_registry(tmp_path)[0]["install_status"] == "not-installed"
    utils.write_text_atomic(tmp_path / "two.yaml", utils.yaml_safe_dump(record))
    with pytest.raises(utils.OCFError, match="duplicate"):
        load_registry(tmp_path)
    (tmp_path / "two.yaml").unlink()
    record["bundled"] = True
    utils.write_text_atomic(tmp_path / "one.yaml", utils.yaml_safe_dump(record))
    with pytest.raises(utils.OCFError, match="metadata"):
        load_registry(tmp_path)


def test_canonical_text_fingerprint_is_checked_before_decode(tmp_path):
    doc, manifest, source = package(tmp_path)
    manifest["recordings"]["first"]["text_sha256"] = "0" * 64
    source.write_text(utils.yaml_safe_dump(manifest))
    with pytest.raises(utils.OCFError, match="canonical narration text changed"):
        prepare_recordings(source, doc, "en-US")


def test_documentation_checker_ignores_build_artifacts_not_authored_docs(tmp_path, monkeypatch):
    from tools import check_markdown_links as checker

    (tmp_path / "build").mkdir()
    (tmp_path / "build/staged.md").write_text("[not runtime documentation](missing.md)")
    authored = tmp_path / "source.md"
    authored.write_text("[broken source link](missing.md)")
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    assert checker.iter_markdown() == [authored]
    assert checker.check_file(authored) == [f"{authored}: broken internal link -> missing.md"]
