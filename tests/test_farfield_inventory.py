"""Pinned provenance is checked offline, including local-only historical inputs."""

import json
import subprocess
from pathlib import Path

import pytest
from ocf_tools import farfield
from ocf_tools import farfield_inventory as inventory
from ocf_tools.utils import OCFError


@pytest.mark.integration
def test_committed_inventory_and_contribution_fidelity():
    assert inventory.check() == []
    data = json.loads((inventory.REPO_ROOT / inventory.INVENTORY).read_text(encoding="utf-8"))
    assert len(data["upstream_presets"]) == 19
    mirrors = [r for r in data["presets"] if r["classification"] == "exact-upstream-mirror"]
    assert len(mirrors) == 19
    historical = [r for r in data["presets"] if r["classification"] == "historical-snapshot"]
    assert len(historical) == 3
    assert all(r["current_fidelity"] == "best-effort" for r in historical)
    assert {Path(r["local_path"]).stem for r in historical} == {
        "focus-11-a",
        "focus-11-b",
        "focus-11-c",
    }


@pytest.mark.unit
def test_all_acoustic_fields_are_compared():
    old = b"title: Old\nfidelity: measured-tape\nsegments: [{duration: '30:00'}]\n"
    new = b"title: New\nfidelity: best-effort\nsegments: [{duration: '30:00'}]\n"
    assert inventory.acoustic_inputs(old) == inventory.acoustic_inputs(new)
    assert inventory.acoustic_inputs(new + b"emerge: false\n") != inventory.acoustic_inputs(old)
    with pytest.raises(OCFError, match="mapping"):
        inventory.acoustic_inputs(b"[]")


@pytest.mark.unit
def test_old_cli_success_exit_still_reports_incompatible_fidelity(monkeypatch):
    monkeypatch.setattr(farfield, "check_farfield", lambda: farfield.FarfieldStatus(True, "engine"))
    result = subprocess.CompletedProcess([], 0, "", "unknown fidelity 'best-effort'")
    monkeypatch.setattr(farfield, "workspace_run", lambda *a, **kw: result)
    actual = farfield.run_farfield(["describe", "preset.yaml"])
    assert actual.returncode == 1
    assert farfield.FARFIELD_COMPATIBLE_REVISION in actual.stderr
    assert "Do not relabel" in actual.stderr


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["bytes", "extra", "missing", "duplicate", "mirror"])
def test_offline_inventory_detects_drift(tmp_path, mutation):
    directory = tmp_path / inventory.MIRRORS
    directory.mkdir(parents=True)
    source = directory / "test.yaml"
    source.write_bytes(b"name: test\n")
    row = {
        "local_path": source.relative_to(tmp_path).as_posix(),
        "sha256": inventory.digest(source.read_bytes()),
        "classification": "exact-upstream-mirror",
        "upstream_path": "presets/test.yaml",
    }
    data = {
        "repository": inventory.REPOSITORY,
        "revision": inventory.REVISION,
        "presets": [row],
        "notices": {},
        "upstream_presets": {"presets/test.yaml": row["sha256"]},
    }
    if mutation == "bytes":
        source.write_bytes(b"changed")
    elif mutation == "extra":
        (directory / "extra.yaml").write_bytes(b"extra")
    elif mutation == "missing":
        source.unlink()
    elif mutation == "duplicate":
        data["presets"].append(dict(row))
    else:
        data["upstream_presets"]["presets/test.yaml"] = "incorrect"
    (tmp_path / inventory.INVENTORY).write_text(json.dumps(data), encoding="utf-8")
    assert inventory.check(tmp_path)


@pytest.mark.unit
def test_absent_nonruntime_staging_does_not_break_clean_checkout(tmp_path):
    path = tmp_path / inventory.INVENTORY
    path.parent.mkdir(parents=True)
    data = {
        "repository": inventory.REPOSITORY,
        "revision": inventory.REVISION,
        "presets": [
            {
                "local_path": "presets/farfield/old.yaml",
                "classification": "staging-only-contribution",
                "sha256": "unused",
            }
        ],
        "notices": {},
        "upstream_presets": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert inventory.check(tmp_path) == []
