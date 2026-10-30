"""Coverage math, honest context attribution, and retained-output boundaries."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools import coverage_report as report
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def totals(lines=3, branches=1):
    return {
        "covered_lines": lines,
        "num_statements": 4,
        "missing_lines": 4 - lines,
        "excluded_lines": 0,
        "covered_branches": branches,
        "num_branches": 2,
        "missing_branches": 2 - branches,
    }


def test_statement_and_branch_gates_are_independent_and_exclusions_fail():
    metrics = report.metrics(totals())
    assert metrics["statement_percent"] == 75 and metrics["branch_percent"] == 50
    summary = {"pytest_exit_code": 0, "reports": {"combined": metrics}}
    floors = {"minimums": {"combined": {"statement_percent": 70, "branch_percent": 60}}}
    assert "branch_percent" in report.check(summary, floors)[0]
    metrics["branch_percent"] = 60
    assert report.check(summary, floors) == []
    metrics["excluded_lines"] = 1
    assert "excluded" in report.check(summary, floors)[0]
    summary["pytest_exit_code"] = 1
    summary["taxonomy_errors"] = ["ambiguous-test"]
    assert len(report.check(summary, floors)) == 3
    summary["deselected_count"] = 1
    assert "deselect" in report.check(summary, floors)[-1]
    assert report.metrics(totals(lines=0, branches=0))["statement_percent"] == 0


def test_compact_receipt_source_sha_is_validated(monkeypatch):
    monkeypatch.setattr(
        report.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="a" * 40 + "\n"),
    )
    assert report.source_sha() == "a" * 40
    monkeypatch.setattr(
        report.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="not-a-git-sha\n"),
    )
    assert report.source_sha() is None


def test_existing_output_is_preserved_and_escape_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "work_root", lambda: tmp_path)
    sentinel = tmp_path / "retained.log"
    sentinel.write_text("failed diagnostics", encoding="utf-8")
    with pytest.raises(OCFError, match="already exists"):
        report.run(tmp_path)
    with pytest.raises(OCFError, match="contained"):
        report.run(tmp_path.parent / "outside")
    assert sentinel.read_text() == "failed diagnostics"


@pytest.mark.parametrize("relative", [False, True])
def test_context_reports_do_not_relabel_startup_as_unit_or_sum_contributions(
    tmp_path, monkeypatch, relative
):
    import runpy

    from coverage import Coverage

    source = tmp_path / "src"
    source.mkdir()
    code = source / "original.py"
    code.write_text(
        "def choose(value):\n    if value:\n        return 1\n    return 0\n", encoding="utf-8"
    )
    config = tmp_path / "pyproject.toml"
    config.write_text(
        '[tool.coverage.run]\nbranch = true\nsource = ["'
        + ("src" if relative else source.as_posix())
        + '"]\nrelative_files = '
        + str(relative).lower()
        + "\n[tool.coverage.report]\nexclude_lines = []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(report, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(report, "source_sha", lambda: "a" * 40)
    output = tmp_path / "reports"
    output.mkdir()
    monkeypatch.chdir(tmp_path)
    coverage = Coverage(data_file=str(output / ".coverage"), config_file=str(config))
    coverage.start()
    try:
        namespace = runpy.run_path(str(code))  # Startup has no test context.
        coverage.switch_context("tests/test_demo.py::test_unit|run")
        assert namespace["choose"](True) == 1
        coverage.switch_context("tests/test_demo.py::test_integration|run")
        assert namespace["choose"](False) == 0
    finally:
        coverage.stop()
        coverage.save()
    (output / "collection-serial.json").write_text(
        json.dumps(
            [
                {"nodeid": "tests/test_demo.py::test_unit", "unit": True, "integration": False},
                {
                    "nodeid": "tests/test_demo.py::test_integration",
                    "unit": False,
                    "integration": True,
                },
            ]
        ),
        encoding="utf-8",
    )
    (output / "tests.xml").write_text(
        '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0"/></testsuites>',
        encoding="utf-8",
    )
    preexisting_detail = output / "combined.json"
    preexisting_detail.write_text("keep historical detail\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    summary = report.summarize(output, exit_code=0, elapsed=1)
    assert Path.cwd() == tmp_path.parent
    assert summary["counts"]["passed"] == 2 and summary["taxonomy_errors"] == []
    combined, unit, integration = [
        summary["reports"][name] for name in ("combined", "unit", "integration")
    ]
    assert combined["covered_lines"] == 4 and combined["covered_branches"] == 2
    assert unit["covered_lines"] == integration["covered_lines"] == 2
    assert unit["covered_branches"] == integration["covered_branches"] == 1
    assert summary["unit_100_percent_achieved"] is False
    assert preexisting_detail.read_text(encoding="utf-8") == "keep historical detail\n"
    assert not list(output.glob(".combined-*.json"))
    import shutil

    detailed_output = tmp_path / "detailed-reports"
    shutil.copytree(output, detailed_output)
    (detailed_output / "combined.json").unlink()
    detailed = report.summarize(detailed_output, exit_code=0, elapsed=1, retain_detail_json=True)
    assert detailed["reports"] == summary["reports"]
    assert (detailed_output / "combined.json").is_file()
    assert (
        json.loads((detailed_output / "combined.json").read_text())["meta"]["show_contexts"] is True
    )


def test_failed_compact_export_retains_partial_report(tmp_path, monkeypatch):
    from coverage import Coverage

    root = tmp_path / "repo"
    root.mkdir()
    (root / "scripts/ocf_tools").mkdir(parents=True)
    (root / "scripts/tools").mkdir()
    (root / "pyproject.toml").write_text("[tool.coverage.run]\nbranch = true\n")
    directory = root / "coverage"
    directory.mkdir()
    coverage_data = Coverage(data_file=str(directory / ".coverage"), config_file=False)
    coverage_data.erase()
    coverage_data.save()
    (directory / "collection-serial.json").write_text(
        json.dumps([{"nodeid": "tests/test.py::test_one", "unit": True, "integration": False}])
    )
    (directory / "tests.xml").write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"/></testsuites>'
    )
    monkeypatch.setattr(report, "REPO_ROOT", root)
    original = Coverage.json_report

    def partial_then_fail(self, *args, **kwargs):
        Path(kwargs["outfile"]).write_text('{"partial": true}')
        raise OSError("fixture report failure")

    monkeypatch.setattr(Coverage, "json_report", partial_then_fail)
    with pytest.raises(OSError, match="fixture report failure"):
        report.summarize(directory, exit_code=0, elapsed=1)
    details = list(directory.glob(".combined-*.json"))
    assert len(details) == 1 and json.loads(details[0].read_text()) == {"partial": True}
    monkeypatch.setattr(Coverage, "json_report", original)


@pytest.mark.parametrize("exit_code", [0, 1])
def test_full_runner_neutralizes_selection_and_cleans_only_successful_scratch(
    tmp_path, monkeypatch, exit_code
):
    monkeypatch.setattr(report, "work_root", lambda: tmp_path)
    monkeypatch.setattr(
        report, "workspace_environment", lambda: {"PYTEST_ADDOPTS": "-k selected_only"}
    )
    scratch = tmp_path / "managed-scratch"
    scratch.mkdir()
    monkeypatch.setattr(report, "workspace_temp_directory", lambda **kwargs: scratch)
    floors = tmp_path / "floors.json"
    floors.write_text(json.dumps({"minimums": {}}), encoding="utf-8")
    monkeypatch.setattr(report, "FLOORS", floors)
    summary = {"pytest_exit_code": exit_code, "taxonomy_errors": [], "deselected_count": 0}
    monkeypatch.setattr(report, "summarize", lambda *args, **kwargs: dict(summary))
    cleaned = []
    monkeypatch.setattr(report, "cleanup_workspace_temp", lambda path: cleaned.append(path) or True)

    def process(command, **kwargs):
        assert "PYTEST_ADDOPTS" not in kwargs["env"]
        assert command[command.index("-o") + 1] == "addopts="
        assert command[command.index("--basetemp") + 1] == str(scratch / "p")
        assert kwargs["cwd"] == report.REPO_ROOT
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(report.subprocess, "run", process)
    ticks = iter([0.0, 10.0, 10.0, 12.0, 12.0])
    monkeypatch.setattr(report, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    directory, result = report.run(tmp_path / "reports")
    assert (directory / "pytest.log").exists()
    assert result["scratch_retained"] is bool(exit_code)
    assert result["reporting_seconds"] == 2.0
    assert result["total_runtime_seconds"] == 12.0
    assert cleaned == ([] if exit_code else [scratch])
