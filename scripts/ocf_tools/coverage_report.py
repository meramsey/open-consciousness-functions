"""Reproducible full-suite coverage, separate statement/branch gates and taxonomy."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from .paths import REPO_ROOT, work_root, workspace_environment
from .utils import OCFError

FLOORS = REPO_ROOT / "tests/coverage-floors.json"


def metrics(totals):
    """Keep statement percentage distinct from coverage.py's combined score."""
    result = {
        key: totals[key]
        for key in (
            "covered_lines",
            "num_statements",
            "missing_lines",
            "excluded_lines",
            "covered_branches",
            "num_branches",
            "missing_branches",
        )
    }
    for prefix, covered, denominator in (
        ("statement", "covered_lines", "num_statements"),
        ("branch", "covered_branches", "num_branches"),
    ):
        result[prefix + "_percent"] = (
            100 * totals[covered] / totals[denominator] if totals[denominator] else 100.0
        )
    return result


def check(summary, floors):
    failures = []
    if summary["pytest_exit_code"] != 0:
        failures.append("full pytest did not pass")
    for name, minimum in floors["minimums"].items():
        report = summary["reports"][name]
        if report["excluded_lines"]:
            failures.append(f"{name}: excluded statements are forbidden")
        for metric in ("statement_percent", "branch_percent"):
            if report[metric] < minimum[metric]:
                failures.append(f"{name}: {metric} {report[metric]:.8f} < {minimum[metric]}")
    if summary.get("taxonomy_errors"):
        failures.append("tests must have exactly one audited unit/integration classification")
    return failures


def summarize(directory, *, exit_code, elapsed):
    from coverage import Coverage

    coverage = Coverage(
        data_file=str(directory / ".coverage"), config_file=str(REPO_ROOT / "pyproject.toml")
    )
    coverage.load()
    rows = {}
    for path in directory.glob("collection-*.json"):
        rows.update({row["nodeid"]: row for row in json.loads(path.read_text(encoding="utf-8"))})
    if not rows:
        raise OCFError("coverage taxonomy collection is missing")
    reports = {}
    for name in ("combined", "unit", "integration"):
        contexts = None
        if name != "combined":
            nodes = [re.escape(node) for node, row in rows.items() if row[name]]
            contexts = ["^(?:" + "|".join(nodes) + ")(?:\\||$)"] if nodes else ["(?!)"]
        coverage.json_report(
            outfile=str(directory / (name + ".json")), contexts=contexts, pretty_print=True
        )
        reports[name] = metrics(
            json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))["totals"]
        )
    root = ET.parse(directory / "tests.xml").getroot()
    suites = list(root.iter("testsuite"))
    counts = {
        name: sum(int(suite.attrib.get(name, 0)) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    result = {
        "schema_version": "1.0",
        "pytest_exit_code": exit_code,
        "runtime_seconds": elapsed,
        "python": platform.python_version(),
        "platform": sys.platform,
        "scope": ["scripts/ocf_tools", "scripts/tools"],
        "workers": 2,
        "taxonomy_errors": [
            node for node, row in rows.items() if row["unit"] == row["integration"]
        ],
        "classified_counts": {
            name: sum(row[name] for row in rows.values()) for name in ("unit", "integration")
        },
        "counts": counts,
        "reports": reports,
        "context_note": "Unit/integration are strict attributed test-context contributions. Combined also includes startup/unattributed subprocess execution; contributions overlap and must not be summed.",
        "unit_100_percent_achieved": reports["unit"]["statement_percent"]
        == reports["unit"]["branch_percent"]
        == 100,
    }
    (directory / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def run(directory=None):
    # No filtering: two workers execute the complete existing suite and all new
    # tests. The shorter basetemp preserves the release path-length guard.
    root = work_root()
    token = uuid.uuid4().hex[:10]
    directory = (directory or root / "logs/coverage" / token).resolve()
    if not directory.is_relative_to(root):
        raise OCFError("coverage output must be contained in OCF_WORK_DIR")
    if directory.exists():
        raise OCFError("coverage output already exists; retain it and choose a new directory")
    directory.mkdir(parents=True)
    environment = workspace_environment()
    environment.update(
        COVERAGE_FILE=str(directory / ".coverage"),
        COVERAGE_RCFILE=str(REPO_ROOT / "pyproject.toml"),
        OCF_COVERAGE_COLLECTION=str(directory),
        PYTHONPATH=os.pathsep.join([str(REPO_ROOT / "scripts"), str(REPO_ROOT / "tests")]),
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "2",
        "--dist",
        "loadfile",
        "-p",
        "coverage_collection",
        "--cov=scripts/ocf_tools",
        "--cov=scripts/tools",
        "--cov-branch",
        "--cov-context=test",
        "--cov-config",
        str(REPO_ROOT / "pyproject.toml"),
        "--cov-report=",
        "--junitxml",
        str(directory / "tests.xml"),
        "--basetemp",
        str(root / ("c-" + token)),
        "-ra",
    ]
    start = time.monotonic()
    with (directory / "pytest.log").open("wb") as log:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    summary = summarize(directory, exit_code=completed.returncode, elapsed=time.monotonic() - start)
    return directory, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("run", help="explicit full-suite measurement; retains diagnostics")
    start.add_argument("--output", type=Path)
    report = sub.add_parser("check", help="check an existing summary; does not run pytest")
    report.add_argument("summary", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            directory, summary = run(args.output)
        else:
            directory = args.summary.parent
            summary = json.loads(args.summary.read_text(encoding="utf-8"))
        failures = check(summary, json.loads(FLOORS.read_text(encoding="utf-8")))
        print(
            json.dumps(
                {"directory": str(directory), "summary": summary, "gate_failures": failures},
                indent=2,
            )
        )
        return 1 if failures else 0
    except (OSError, ValueError, OCFError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
