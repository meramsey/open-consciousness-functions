"""Public CI annotations retain actionable failure details without log access."""

from pathlib import Path

import pytest
import yaml
from conftest import REPO_ROOT
from tools.report_pytest_failures import report_failures

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("outcome", ["failure", "error", "skipped", "missing"])
def test_integration_reporter_only_annotates_actual_failures(
    tmp_path, monkeypatch, capsys, outcome
):
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/test.yml").read_text())
    step = next(
        row
        for row in workflow["jobs"]["integration"]["steps"]
        if row.get("name") == "Report integration failure details"
    )
    assert step["if"] == "failure()"
    assert (
        step["run"]
        == "python scripts/tools/report_pytest_failures.py .ocf-work/logs/pytest-results.xml"
    )
    assert any(row.get("run") == step["run"] for row in workflow["jobs"]["unit"]["steps"])
    assert any(row.get("run") == step["run"] for row in workflow["jobs"]["agent-tools"]["steps"])
    monkeypatch.chdir(tmp_path)
    if outcome != "missing":
        path = Path(".ocf-work/logs/pytest-results.xml")
        path.parent.mkdir(parents=True)
        path.write_bytes(
            (
                '<testsuite><testcase classname="tests.test_fixture" name="test_unicode">'
                f"<{outcome}>Café: expected 100%&#13;\nactual regression</{outcome}>"
                "</testcase></testsuite>"
            ).encode()
        )
    count = report_failures(Path(".ocf-work/logs/pytest-results.xml"))
    output = capsys.readouterr().out
    if outcome in {"failure", "error"}:
        assert count == 1
        assert "::error title=Pytest failure::" in output
        assert "tests.test_fixture::test_unicode%0A" in output
        assert "100%25%0D%0Aactual regression" in output
    else:
        assert count == 0 and output == ""
