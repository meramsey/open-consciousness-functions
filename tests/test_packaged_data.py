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
