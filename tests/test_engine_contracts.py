"""Optional-engine planning and detection with a stubbed native process boundary."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from ocf_tools import audio, farfield, sbagenx

pytestmark = pytest.mark.unit


def result(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.mark.parametrize(
    "module,status_cls,probe",
    [
        (farfield, farfield.FarfieldStatus, "--version"),
        (sbagenx, sbagenx.SbagenxStatus, "-h"),
    ],
)
@pytest.mark.parametrize(
    "outcome", ["missing", "stdout", "stderr", "nonzero", "empty", "oserror", "timeout"]
)
def test_detection_probes_and_failures(monkeypatch, tmp_path, module, status_cls, probe, outcome):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    name = "farfield" if module is farfield else "sbagenx"
    monkeypatch.setattr(
        module.shutil, "which", lambda requested: None if outcome == "missing" else "engine"
    )
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if outcome == "oserror":
            raise OSError("gone")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(argv, 8)
        text = "farfield 1.2" if module is farfield else "header\nSBaGenX version v2.3\nfooter"
        return result(
            7 if outcome == "nonzero" else 0,
            text if outcome in ("stdout", "nonzero") else "",
            text if outcome == "stderr" else "",
        )

    monkeypatch.setattr(module.subprocess, "run", run)
    status = getattr(module, "check_" + name)()
    assert isinstance(status, status_cls)
    assert status.available is (outcome != "missing")
    if outcome == "missing":
        assert not calls and status.executable is None
    else:
        argv, kwargs = calls[0]
        assert argv == ["engine", probe]
        assert kwargs["capture_output"] is True and kwargs["text"] is True
        assert kwargs["timeout"] == 8
        temporary_path = Path(kwargs["env"]["TMPDIR"])
        assert temporary_path.parent == (tmp_path / "ocf-work" / "tmp").resolve()
        expected = "farfield 1.2" if module is farfield else "2.3"
        assert status.version == (
            expected
            if outcome in ("stdout", "stderr") or (module is sbagenx and outcome == "nonzero")
            else None
        )


@pytest.mark.parametrize(
    "module,status_cls,error_cls,name",
    [
        (farfield, farfield.FarfieldStatus, farfield.OCFFarfieldMissing, "farfield"),
        (sbagenx, sbagenx.SbagenxStatus, sbagenx.OCFSbagenxMissing, "sbagenx"),
    ],
)
def test_public_run_missing_and_argv_boundary(
    monkeypatch, tmp_path, module, status_cls, error_cls, name
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    monkeypatch.setattr(module, "check_" + name, lambda: status_cls(True, None))
    with pytest.raises(error_cls, match="optional"):
        getattr(module, "run_" + name)(["anything"])
    monkeypatch.setattr(module, "check_" + name, lambda: status_cls(True, "engine"))
    calls = []
    response = result(stdout="fixture")
    monkeypatch.setattr(
        module.subprocess, "run", lambda argv, **kwargs: calls.append((argv, kwargs)) or response
    )
    assert getattr(module, "run_" + name)(["--fixture", "with spaces"]) is response
    argv, kwargs = calls[0]
    assert argv == ["engine", "--fixture", "with spaces"]
    assert kwargs["check"] is False and kwargs["text"] is True and kwargs["capture_output"] is True
    assert Path(kwargs["env"]["TMPDIR"]).parent == (tmp_path / "ocf-work" / "tmp").resolve()


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "unreadable",
        "empty",
        "noshebang",
        "notvenv",
        "norecord",
        "badjson",
        "list",
        "numeric",
        "remote",
        "remote-file",
        "malformed-url",
        "absent",
        "local",
        "escaped",
        "localhost",
    ],
)
def test_checkout_metadata_is_optional_local_and_decoded(monkeypatch, tmp_path, case):
    launcher = tmp_path / "bin/farfield"
    launcher.parent.mkdir()
    interpreter = tmp_path / "bin/python"
    launcher.write_text(f"#!{interpreter}\n")
    source = tmp_path / ("source tree" if case == "escaped" else "source")
    if case in ("local", "escaped", "localhost"):
        (source / "presets").mkdir(parents=True)
    info = tmp_path / "lib/python3.12/site-packages/farfield-0.1.dist-info"
    info.mkdir(parents=True)
    data = {"url": source.as_uri()}
    if case == "localhost":
        data["url"] = data["url"].replace("file:///", "file://localhost/")
    if case == "list":
        data = []
    elif case == "numeric":
        data = {"url": 1}
    elif case == "remote":
        data = {"url": "https://example.invalid/source"}
    elif case == "remote-file":
        data = {"url": "file://remote.invalid/source"}
    elif case == "malformed-url":
        data = {"url": "file://[invalid/source"}
    if case != "norecord":
        (info / "direct_url.json").write_text("{broken" if case == "badjson" else json.dumps(data))
    if case == "empty":
        launcher.write_text("")
    elif case == "noshebang":
        launcher.write_text("plain launcher")
    elif case == "notvenv":
        launcher.write_text("#!/usr/python\n")
    elif case == "unreadable":
        launcher.unlink()
    monkeypatch.setattr(
        farfield.shutil, "which", lambda name: None if case == "missing" else str(launcher)
    )
    assert farfield._source_preset_dirs() == (
        [source / "presets"] if case in ("local", "escaped", "localhost") else []
    )


def test_preset_precedence_paths_extensions_and_report(monkeypatch, tmp_path):
    repo, override, extension = tmp_path / "repo", tmp_path / "override", tmp_path / "external"
    mirror = repo / "audio/background/presets/farfield"
    for folder in (override, mirror, extension):
        folder.mkdir(parents=True)
        (folder / "same.yaml").write_text("fixture")
    monkeypatch.setattr(farfield, "REPO_ROOT", repo)
    monkeypatch.setattr(farfield, "_source_preset_dirs", lambda: [extension])
    monkeypatch.setenv("OCF_FARFIELD_PRESETS_DIR", str(override) + os.pathsep + "")
    assert farfield.farfield_preset_dirs() == [override, mirror, mirror.parent, extension]
    assert farfield.resolve_preset("same") == override / "same.yaml"
    monkeypatch.delenv("OCF_FARFIELD_PRESETS_DIR")
    assert farfield.resolve_preset("same") == mirror / "same.yaml"
    assert farfield.resolve_preset(str(extension / "same.yaml")) == extension / "same.yaml"
    (extension / "other.yml").write_text("fixture")
    assert farfield.resolve_preset("other") == extension / "other.yml"
    assert farfield.resolve_preset(str(extension / "other.yml")) == extension / "other.yml"
    assert farfield.resolve_preset("unknown") is None
    monkeypatch.setattr(farfield, "farfield_preset_dirs", lambda: [mirror, tmp_path / "absent"])
    report = farfield.preset_search_report("unknown")
    assert "(exists)" in report and "(missing)" in report and "OCF_FARFIELD_PRESETS_DIR" in report


def test_farfield_command_results_and_missing_guidance(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(farfield, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        farfield, "run_farfield", lambda argv: calls.append(argv) or result(stdout="ok")
    )
    assert "ok" in farfield.describe_preset("p")
    assert "ok" in farfield.list_background_presets()
    assert "Rendered" in farfield.render_preset("p", output=tmp_path / "out.wav", seed=0)
    assert calls[-1] == ["render", "p", "--output", str(tmp_path / "out.wav"), "--seed", "0"]
    assert "p-x.wav" in farfield.render_preset("p:x")
    monkeypatch.setattr(farfield, "run_farfield", lambda argv: result(4, stderr="render error"))
    assert "exit 4" in farfield.render_preset("p")

    def missing(argv):
        raise farfield.OCFFarfieldMissing("optional missing")

    monkeypatch.setattr(farfield, "run_farfield", missing)
    assert farfield.describe_preset("p") == "optional missing"
    assert farfield.render_preset("p") == "optional missing"
    assert farfield.list_background_presets() == "optional missing"


def test_sbagenx_planning_failure_and_stale_output(monkeypatch, tmp_path):
    monkeypatch.setattr(sbagenx, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sbagenx, "check_sbagenx", lambda: sbagenx.SbagenxStatus(False))
    assert "optional" in sbagenx.list_programs()
    monkeypatch.setattr(sbagenx, "check_sbagenx", lambda: sbagenx.SbagenxStatus(True, "engine"))
    assert all(name in sbagenx.list_programs() for name in sbagenx.BUILTIN_PROGRAMS)
    calls = []
    monkeypatch.setattr(
        sbagenx, "run_sbagenx", lambda argv: calls.append(argv) or result(stdout="sequence")
    )
    assert "sequence" in sbagenx.describe_preset("p.sbg")
    assert "failed" in sbagenx.render_preset("p.sbg")
    out = tmp_path / "out.wav"
    out.write_bytes(b"old output")
    assert "Rendered" in sbagenx.render_preset("p.sbg", output=out, sample_rate=22050)
    assert calls[-1] == ["-SE", "-q", "1", "-r", "22050", "-Q", "-Wo", str(out), "p.sbg"]
    monkeypatch.setattr(sbagenx, "run_sbagenx", lambda argv: result(5, stdout="failed stdout"))
    assert "exit 5" in sbagenx.describe_preset("p.sbg")
    assert "failed" in sbagenx.render_preset("p.sbg", output=out)
    assert out.read_bytes() == b"old output"

    def missing(argv):
        raise sbagenx.OCFSbagenxMissing("optional missing")

    monkeypatch.setattr(sbagenx, "run_sbagenx", missing)
    assert sbagenx.describe_preset("p") == "optional missing"
    assert sbagenx.render_preset("p") == "optional missing"


@pytest.mark.parametrize("available,version", [(False, None), (True, None), (True, "1.2")])
def test_audio_handler_detection_messages(monkeypatch, capsys, available, version):
    monkeypatch.setattr(
        audio.farfield_mod,
        "check_farfield",
        lambda: farfield.FarfieldStatus(available, "engine", version),
    )
    monkeypatch.setattr(
        audio.sbagenx_mod,
        "check_sbagenx",
        lambda: sbagenx.SbagenxStatus(available, "engine", version),
    )
    assert audio.check_engine() == 0
    text = capsys.readouterr().out
    assert ("NOT AVAILABLE" in text) is (not available)
    assert ("version:" in text) is bool(version)


def test_audio_manifest_resolution_planning_and_overrides(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(audio, "REPO_ROOT", tmp_path)
    preset = tmp_path / "preset.yaml"
    preset.write_text("fixture")
    manifest = {
        "id": "OCF-BG-9999",
        "name": "Fixture",
        "engine": "farfield",
        "preset": {"file": "preset.yaml"},
        "render": {"output": "bed.wav", "seed": 0, "deterministic": True},
    }
    monkeypatch.setattr(audio, "load_background_manifests", lambda: [manifest])
    assert audio._find_manifest("OCF-BG-9999.yaml") == manifest
    assert audio._find_manifest(" fixture ") == manifest
    assert audio._preset_engine_file("Fixture") == str(preset)
    calls = []
    monkeypatch.setattr(
        audio.farfield_mod, "render_preset", lambda p, **kw: calls.append((p, kw)) or "planned"
    )
    assert audio.render_background("Fixture") == 0
    assert calls[-1] == (str(preset), {"output": tmp_path / "bed.wav", "seed": 0})
    assert "Deterministic" in capsys.readouterr().out
    assert audio.render_background("Fixture", str(tmp_path / "override.wav")) == 0
    assert calls[-1][1]["output"] == tmp_path / "override.wav"
    monkeypatch.setattr(
        audio.sbagenx_mod, "render_preset", lambda p, **kw: calls.append((p, kw)) or "planned"
    )
    assert audio.render_background("unknown", engine="sbagenx") == 0
    assert calls[-1] == ("unknown", {"output": None})
    assert audio.render_background("unknown", engine="farfield") == 0
    assert calls[-1] == ("unknown", {"output": None, "seed": None})
    monkeypatch.setattr(audio.farfield_mod, "describe_preset", lambda p: "ff " + p)
    monkeypatch.setattr(audio.sbagenx_mod, "describe_preset", lambda p: "sb " + p)
    assert audio.describe_background("Fixture") == 0
    assert audio.describe_background("unknown", engine="sbagenx") == 0
    assert "sb unknown" in capsys.readouterr().out
    monkeypatch.setattr(audio.farfield_mod, "list_background_presets", lambda: "ff list")
    monkeypatch.setattr(audio.sbagenx_mod, "list_programs", lambda: "sb list")
    assert audio.list_background() == 0
    assert "Fixture" in capsys.readouterr().out
    manifest["preset"] = {}
    manifest["render"] = {}
    assert audio._preset_engine_file("Fixture") is None
    assert audio.render_background("Fixture") == 0
    assert calls[-1] == ("Fixture", {"output": None, "seed": None})
    manifest["preset"] = {"file": "missing.yaml"}
    assert audio._preset_engine_file("Fixture") is None
    monkeypatch.setattr(audio, "load_background_manifests", lambda: [])
    assert audio.list_background() == 0
    assert "none recorded" in capsys.readouterr().out
