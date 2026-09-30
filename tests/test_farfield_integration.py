"""Farfield integration tests: graceful degradation and command construction."""

from __future__ import annotations

from pathlib import Path

import pytest
from ocf_tools import farfield
from ocf_tools.audio import check_engine, describe_background, render_background


class _Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture()
def no_farfield(monkeypatch):
    monkeypatch.setattr(farfield.shutil, "which", lambda name: None)
    monkeypatch.setattr(farfield.subprocess, "run", lambda *a, **k: _Result())
    return None


def _fake_run_factory(calls):
    def fake_run(args, **_):
        # farfield is invoked as `farfield <subcommand> ...` via its PATH entry,
        # so args[-1] position is never safe; the subcommand is args[1].
        calls.append(list(args))
        sub = args[1] if len(args) > 1 else ""
        if sub == "--version":
            return _Result(stdout="farfield 1.0\n")
        if sub == "list":
            return _Result(stdout="preset-a\npreset-b\n")
        if sub == "describe":
            return _Result(stdout="described\n")
        if sub == "render":
            return _Result(stdout="rendered\n")
        return _Result()

    return fake_run


@pytest.fixture()
def fake_farfield(monkeypatch):
    monkeypatch.setattr(farfield.shutil, "which", lambda name: "/usr/bin/farfield")
    calls = []
    monkeypatch.setattr(farfield.subprocess, "run", _fake_run_factory(calls))
    return calls


def test_check_farfield_missing_reports_guidance(no_farfield):
    status = farfield.check_farfield()
    assert status.available is False
    assert "farfield" in farfield.installation_guidance()


def test_check_engine_degrades_gracefully(no_farfield, capsys):
    assert check_engine() == 0
    out = capsys.readouterr().out
    assert "NOT AVAILABLE" in out
    assert "https://github.com/txus/farfield" in out


def test_render_background_missing_no_crash(no_farfield, capsys):
    assert render_background("OCF-BG-0001", None) == 0
    out = capsys.readouterr().out
    assert "farfield" in out and "install" in out


def test_describe_background_missing_no_crash(no_farfield, capsys):
    assert describe_background("any-preset") == 0
    out = capsys.readouterr().out
    assert "farfield is not installed" in out


def test_farfield_command_construction(fake_farfield, capsys, tmp_path):
    output = Path(tmp_path) / "out.wav"
    result_text = farfield.render_preset("OCF-BG-0001", output=output, seed=7)
    assert "Rendered to" in result_text
    assert "--seed" in result_text
    args = fake_farfield[-1]
    assert args[1] == "render"
    assert "--output" in args


def test_farfield_public_cli_only(fake_farfield):
    result = farfield.run_farfield(["list"])
    assert result.stdout == "preset-a\npreset-b\n"
    for call in fake_farfield:
        assert call[0].endswith("farfield")
        assert call[1] in ("--version", "list", "describe", "render")


def test_list_background_includes_ocf_presets(fake_farfield, capsys):
    from ocf_tools.audio import list_background

    assert list_background() == 0
    out = capsys.readouterr().out
    assert "OCF background presets (manifests)" in out
    assert "OCF-BG-" in out or "(none recorded" in out
    assert "preset-a" in out


class TestLocalPresetResolution:
    """Farfield/SBaGenX are fed the manifest's local preset file, so the OCF
    mirrors under audio/background/presets/ are what actually renders."""

    def test_manifest_preset_file_resolves(self):
        from ocf_tools.audio import _preset_engine_file
        from ocf_tools.paths import REPO_ROOT

        resolved = _preset_engine_file("OCF-BG-0007")
        assert resolved is not None
        assert Path(resolved).is_file()
        assert Path(resolved) == (
            REPO_ROOT / "audio/background/presets/farfield/focus-11-c.yaml"
        )

    def test_sbagenx_manifest_resolves_local_sequence(self):
        from ocf_tools.audio import _preset_engine_file
        from ocf_tools.paths import REPO_ROOT

        resolved = _preset_engine_file("OCF-BG-0010")
        assert Path(resolved) == (
            REPO_ROOT / "audio/background/presets/sbagenx/focus-11-c.sbg"
        )

    def test_unknown_preset_returns_none(self):
        from ocf_tools.audio import _preset_engine_file

        assert _preset_engine_file("no-such-preset") is None

    def test_describe_uses_local_preset_file(self, fake_farfield):
        from ocf_tools.audio import describe_background
        from ocf_tools.paths import REPO_ROOT

        assert describe_background("OCF-BG-0007") == 0
        args = fake_farfield[-1]
        assert args[1] == "describe"
        assert args[2] == str(REPO_ROOT / "audio/background/presets/farfield/focus-11-c.yaml")

    def test_render_uses_local_preset_file(self, fake_farfield, tmp_path):
        from ocf_tools.audio import render_background
        from ocf_tools.paths import REPO_ROOT

        assert render_background("OCF-BG-0007", str(tmp_path / "out.wav")) == 0
        args = fake_farfield[-1]
        assert args[1] == "render"
        assert args[2] == str(REPO_ROOT / "audio/background/presets/farfield/focus-11-c.yaml")


def test_sbagenx_presets_use_supported_rate():
    """Regression: `-R 1000` made sbagenx abort with an FPE; the mirrors ship
    the supported `-R 10` recalculation rate."""
    from ocf_tools.paths import REPO_ROOT

    for name in ("a", "b", "c"):
        text = (
            REPO_ROOT / "audio/background/presets/sbagenx" / f"focus-11-{name}.sbg"
        ).read_text()
        assert "-R 10" in text
        assert "-R 1000" not in text
