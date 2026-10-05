"""Setup plans must be reversible, explicit and preserve conflicting user paths."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools.bootstrap import apply_setup, setup_plan


def test_dry_run_and_windows_adapter_do_not_create_files(tmp_path):
    target = tmp_path / "environment with spaces"
    plan = setup_plan(target, system="Windows")
    assert plan["dry_run"] and not target.exists()
    assert Path(plan["interpreter"]).parts[-2:] == ("Scripts", "python.exe")
    assert plan["optional_installs"] == [] and len(plan["commands"]) == 3
    target.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        setup_plan(target)
    (target / "pyvenv.cfg").write_text("home = custom\n")
    assert setup_plan(target)["reuse"]


def test_applied_setup_checks_reused_runtime_and_fails_clearly(tmp_path, monkeypatch):
    from ocf_tools import bootstrap

    # This contract simulates a supported setup interpreter regardless of the
    # Python version running pytest; the separate compatibility check below
    # exercises rejection of a too-old created environment.
    monkeypatch.setattr(bootstrap, "sys", SimpleNamespace(version_info=(3, 12, 0)))
    target = tmp_path / "env"
    target.mkdir()
    (target / "pyvenv.cfg").write_text("home = custom\n")
    plan = setup_plan(target)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            returncode=0, stdout="3.12" if "-c" in command else '{"ok":true}', stderr=""
        )

    result = apply_setup(plan, runner=run)
    assert result["completed"] and result["doctor"]["ok"]
    assert all("venv" not in command for command in calls)
    with pytest.raises(ValueError, match="incompatible"):
        apply_setup(
            plan, runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="3.9", stderr="")
        )


def test_setup_cli_dry_run_and_conflict_error(tmp_path, capsys):
    import json

    from ocf_tools.bootstrap import main

    target = tmp_path / "new"
    assert main(["--venv", str(target)]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] and not target.exists()
    target.mkdir()
    with pytest.raises(SystemExit) as error:
        main(["--venv", str(target)])
    assert error.value.code == 2
