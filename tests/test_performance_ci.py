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
