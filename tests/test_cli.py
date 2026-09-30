"""CLI entry-point, help, doctor, and validation routing tests."""

from __future__ import annotations

import subprocess
import sys

from conftest import REPO_ROOT


def test_no_args_prints_help(capsys):
    from ocf_tools.cli import main

    assert main([]) == 0
    assert "ocf new function" in capsys.readouterr().out


def test_help_command(capsys):
    from ocf_tools.cli import main

    assert main(["help"]) == 0
    out = capsys.readouterr().out
    assert "ocf audio check-engine" in out
    assert "ocf build-index" in out


def test_doctor_reports_environment(capsys):
    from ocf_tools.cli import main

    code = main(["doctor"])
    out = capsys.readouterr().out
    assert "repository root" in out
    assert "farfield engine" in out
    assert code in (0, 1)  # farfield missing may or may not be counted


def test_validate_all_returns_success(capsys):
    from ocf_tools.cli import main

    assert main(["validate", "--all"]) == 0
    out = capsys.readouterr().out
    assert "0 errors" in out


def test_validate_single_file(sample_function_path, capsys):
    from ocf_tools.cli import main

    assert main(["validate", str(sample_function_path)]) == 0
    assert "0 errors" in capsys.readouterr().out


def test_build_index_check_fresh(capsys):
    from ocf_tools.cli import main

    assert main(["build-index", "--check"]) == 0
    assert "fresh" in capsys.readouterr().out


def test_review_commands_does_not_crash(capsys):
    from ocf_tools.cli import main

    assert main(["review", "commands"]) == 0
    assert "Command review report" in capsys.readouterr().out


def test_unknown_audio_subcommand_prints_help(capsys):
    from ocf_tools.cli import main

    assert main(["audio", "bogus"]) == 0
    assert "ocf new function" in capsys.readouterr().out


def test_ocf_py_entrypoint_via_subprocess():
    result = subprocess.run(
        [sys.executable, "scripts/ocf.py", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ocf new proposal" in result.stdout
