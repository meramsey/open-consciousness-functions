"""SBaGenX integration tests: graceful degradation and command construction."""

from __future__ import annotations

from pathlib import Path

import pytest
from ocf_tools import sbagenx
from ocf_tools.audio import describe_background, render_background


class _Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture()
def no_sbagenx(monkeypatch):
    monkeypatch.setattr(sbagenx.shutil, "which", lambda name: None)
    monkeypatch.setattr(sbagenx.subprocess, "run", lambda *a, **k: _Result())
    return None


def _fake_run_factory(calls):
    def fake_run(args, **_):
        calls.append(list(args))
        # sbagenx has no subcommands; options are positional switches.
        if "-h" in args:
            return _Result(stdout="SbaGenX version 2.0.0\nusage: sbagenx ...\n")
        if "-D" in args:
            return _Result(stdout="  interpreted sequence\n")
        if "-Wo" in args:
            idx = args.index("-Wo")
            if idx + 1 < len(args):
                Path(args[idx + 1]).touch()
        return _Result()

    return fake_run


@pytest.fixture()
def fake_sbagenx(monkeypatch, tmp_path):
    monkeypatch.setattr(sbagenx.shutil, "which", lambda name: "/usr/bin/sbagenx")
    calls = []
    monkeypatch.setattr(sbagenx.subprocess, "run", _fake_run_factory(calls))
    return calls, tmp_path


def test_check_sbagenx_missing_reports_guidance(no_sbagenx):
    status = sbagenx.check_sbagenx()
    assert status.available is False
    assert "sbagenx" in sbagenx.installation_guidance()


def test_check_sbagenx_detects_version(fake_sbagenx):
    status = sbagenx.check_sbagenx()
    assert status.available is True
    assert status.version == "2.0.0"


def test_describe_background_missing_no_crash(no_sbagenx, capsys):
    assert describe_background("any-sbg", engine="sbagenx") == 0
    out = capsys.readouterr().out
    assert "sbagenx is not installed" in out


def test_render_background_missing_no_crash(no_sbagenx, capsys):
    assert render_background("OCF-BG-0001", None, engine="sbagenx") == 0
    out = capsys.readouterr().out
    assert "sbagenx is not installed" in out


def test_sbagenx_command_construction(fake_sbagenx, capsys, tmp_path):
    calls, _ = fake_sbagenx
    output = Path(tmp_path) / "out.wav"
    result_text = sbagenx.render_preset("focus.sbg", output=output)
    assert "Rendered to" in result_text
    args = calls[-1]
    assert "-SE" in args and "-Wo" in args and "--" not in args
    assert str(output) in args
    assert "-D" not in args


def test_sbagenx_public_cli_only(fake_sbagenx):
    result = sbagenx.run_sbagenx(["-h"])
    assert "SbaGenX" in result.stdout
    calls, _ = fake_sbagenx
    for call in calls:
        assert call[0].endswith("sbagenx")
        assert any(flag in call for flag in ("-h", "-D", "-SE", "-Wo"))


def test_describe_preset_uses_dump_flag(fake_sbagenx, tmp_path):
    calls, _ = fake_sbagenx
    preset = tmp_path / "focus.sbg"
    preset.write_text("0ds+ 001:00\n")
    result = sbagenx.describe_preset(str(preset))
    assert "interpreted sequence" in result
    assert "-D" in calls[-1]