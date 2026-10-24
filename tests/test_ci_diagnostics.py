"""Public CI annotations retain actionable failure details without log access."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml
from conftest import REPO_ROOT

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
    source = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    monkeypatch.chdir(tmp_path)
    if outcome != "missing":
        path = Path(".ocf-work/logs/integration-results.xml")
        path.parent.mkdir(parents=True)
        suite = ET.Element("testsuite")
        case = ET.SubElement(suite, "testcase", classname="tests.test_fixture", name="test_unicode")
        ET.SubElement(case, outcome).text = "Café: expected 100%\r\nactual regression"
        ET.ElementTree(suite).write(path, encoding="utf-8")
        path.write_bytes(path.read_bytes().replace(b"\r", b"&#13;"))
    exec(compile(source, "integration_failure_reporter", "exec"), {})
    output = capsys.readouterr().out
    if outcome in {"failure", "error"}:
        assert "::error title=Pytest integration failure::" in output
        assert "tests.test_fixture::test_unicode%0A" in output
        assert "100%25%0D%0Aactual regression" in output
    else:
        assert output == ""
