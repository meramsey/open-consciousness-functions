"""Performance branches must run the existing mandatory verification workflows."""

import pytest
import yaml
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def test_performance_pushes_run_all_existing_verification_workflows():
    branches = {
        "main",
        "perf/test-execution-20261106",
        "perf/bulk-generation-20261106",
        "codex/integrate-test-performance-20261107",
        "codex/integrate-bulk-performance-20261107",
    }
    for name in ("test", "lint", "validate", "generated-index-check"):
        data = yaml.safe_load((REPO_ROOT / f".github/workflows/{name}.yml").read_text())
        events = data.get("on", data.get(True))
        assert set(events["push"]["branches"]) == branches
        assert "pull_request" in events
    tests = yaml.safe_load((REPO_ROOT / ".github/workflows/test.yml").read_text())
    assert {"unit", "integration", "coverage"} <= tests["jobs"].keys()
    assert tests["jobs"]["unit"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.12"]


@pytest.mark.parametrize(
    "name,reports",
    [
        ("synthetic-audio-benchmark", ".ocf-work/audio-benchmark-reports/"),
        ("session-planning-benchmark", ".ocf-work/planning-benchmark/"),
    ],
)
def test_optional_benchmarks_are_manual_and_upload_only_scoped_reports(name, reports):
    data = yaml.safe_load((REPO_ROOT / f".github/workflows/{name}.yml").read_text())
    assert set(data.get("on", data.get(True))) == {"workflow_dispatch"}
    assert data["permissions"] == {"contents": "read"}
    job = next(iter(data["jobs"].values()))
    assert job["timeout-minutes"] <= 30
    upload = next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload["with"]["include-hidden-files"] is True
    assert upload["with"]["path"] == reports
