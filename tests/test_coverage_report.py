"""Coverage math, honest context attribution, and retained-output boundaries."""

import json

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
    assert report.metrics(totals(lines=0, branches=0))["statement_percent"] == 0


def test_existing_output_is_preserved_and_escape_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "work_root", lambda: tmp_path)
    sentinel = tmp_path / "retained.log"
    sentinel.write_text("failed diagnostics", encoding="utf-8")
    with pytest.raises(OCFError, match="already exists"):
        report.run(tmp_path)
    with pytest.raises(OCFError, match="contained"):
        report.run(tmp_path.parent / "outside")
    assert sentinel.read_text() == "failed diagnostics"


def test_context_reports_do_not_relabel_startup_as_unit_or_sum_contributions(tmp_path, monkeypatch):
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
        + source.as_posix()
        + '"]\n[tool.coverage.report]\nexclude_lines = []\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(report, "REPO_ROOT", tmp_path)
    output = tmp_path / "reports"
    output.mkdir()
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
    summary = report.summarize(output, exit_code=0, elapsed=1)
    assert summary["counts"]["passed"] == 2 and summary["taxonomy_errors"] == []
    combined, unit, integration = [
        summary["reports"][name] for name in ("combined", "unit", "integration")
    ]
    assert combined["covered_lines"] == 4 and combined["covered_branches"] == 2
    assert unit["covered_lines"] == integration["covered_lines"] == 2
    assert unit["covered_branches"] == integration["covered_branches"] == 1
    assert summary["unit_100_percent_achieved"] is False
