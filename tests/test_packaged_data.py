"""Source and wheel data discovery must not depend on the caller's directory."""

import pytest
from ocf_tools.paths import resolve_data_root
from tools.build_package_data import stage_data


def fixture_root(root):
    (root / "schemas").mkdir(parents=True)
    (root / "functions").mkdir()
    return root


def test_source_packaged_override_and_missing_data(tmp_path, monkeypatch):
    source = fixture_root(tmp_path / "checkout")
    module = source / "scripts/ocf_tools/paths.py"
    assert resolve_data_root(module) == source
    packaged = fixture_root(tmp_path / "installed-data")
    monkeypatch.chdir(tmp_path)
    assert resolve_data_root(tmp_path / "venv/lib/ocf_tools/paths.py", bundled=packaged) == packaged
    assert resolve_data_root(module, str(packaged)) == packaged
    with pytest.raises(RuntimeError, match="OCF_DATA_ROOT"):
        resolve_data_root(module, str(tmp_path / "absent"))
    with pytest.raises(RuntimeError, match="reinstall"):
        resolve_data_root(tmp_path / "missing/package/paths.py", bundled=tmp_path / "absent")


def test_packaging_excludes_source_wording_and_binary_assets(tmp_path):
    root = fixture_root(tmp_path / "root")
    directory = root / "audio/templates/sessions"
    directory.mkdir(parents=True)
    (directory / "original.yaml").write_text("origin: original-ocf\n")
    (directory / "reference.yaml").write_text("origin: reference-derived\n")
    (root / "functions/audio.wav").write_bytes(b"never bundled")
    output = tmp_path / "staged"
    report = stage_data(root, output)
    assert (output / "audio/templates/sessions/original.yaml").exists()
    assert not (output / "audio/templates/sessions/reference.yaml").exists()
    assert not (output / "functions/audio.wav").exists()
    assert report["omitted_citation_only_bindings"] == ["audio/templates/sessions/reference.yaml"]


def test_packaging_refuses_targets_containing_source_and_target_symlinks(tmp_path):
    root = fixture_root(tmp_path / "root")
    with pytest.raises(ValueError, match="must not contain the source root"):
        stage_data(root, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "target-link"
    try:
        target.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(ValueError, match="must not be a symlink"):
        stage_data(root, target)


def test_package_staging_excludes_citation_binding_and_unsupported_suffixes(tmp_path):
    root = fixture_root(tmp_path / "root")
    binding = root / "function-content/bindings/OCF-FND-002.yaml"
    binding.parent.mkdir(parents=True)
    binding.write_text("function_id: OCF-FND-002\n")
    (root / "schemas/ignored.bin").write_bytes(b"not package data")
    output = tmp_path / "package"
    report = stage_data(root, output)
    assert "function-content/bindings/OCF-FND-002.yaml" in report["omitted_citation_only_bindings"]
    assert not (output / "function-content/bindings/OCF-FND-002.yaml").exists()
    assert not (output / "schemas/ignored.bin").exists()


def test_build_command_writes_package_manifest_after_copy(monkeypatch, tmp_path):
    import json

    from setuptools import Distribution
    from setuptools.command.build_py import build_py
    from tools import build_package_data

    called = {}
    monkeypatch.setattr(build_py, "run", lambda _self: None)

    def stage(root, target):
        called.update(root=root, target=target)
        target.mkdir(parents=True)
        return {"included": ["fixture.yaml"], "omitted_citation_only_bindings": []}

    monkeypatch.setattr(build_package_data, "stage_data", stage)
    command = build_package_data.BuildWithData(Distribution())
    command.build_lib = str(tmp_path / "build")
    command.run()
    manifest = tmp_path / "build/ocf_tools/data/package-data-manifest.json"
    assert json.loads(manifest.read_text()) == {
        "included": ["fixture.yaml"],
        "omitted_citation_only_bindings": [],
    }
    assert called["target"] == manifest.parent
