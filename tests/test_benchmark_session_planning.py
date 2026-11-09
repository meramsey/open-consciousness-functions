"""Planning benchmark metadata and bounds; real plan regressions stay integration."""

import json
from types import SimpleNamespace

import pytest
from tools import benchmark_session_planning as benchmark

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("all_functions", [False, True])
def test_planning_benchmark_reports_every_selected_identity(monkeypatch, capsys, all_functions):
    calls = []

    def plan(identity):
        calls.append(identity)
        return {"function_id": identity}, {"shared": "public"}, {"expanded": True}

    monkeypatch.setattr(benchmark, "source_plan", plan)
    monkeypatch.setattr(
        benchmark,
        "load_all_functions",
        lambda: [SimpleNamespace(id="OCF-TST-001"), SimpleNamespace(id="OCF-TST-002")],
    )
    monkeypatch.setattr(
        benchmark.subprocess,
        "check_output",
        lambda argv, **kw: "b" * 40 if "rev-parse" in argv else "",
    )
    monkeypatch.setattr(
        "sys.argv", ["benchmark", "--iterations", "2", *(["--all"] if all_functions else [])]
    )
    benchmark.main()
    report = json.loads(capsys.readouterr().out)
    assert len(calls) == (4 if all_functions else 2)
    assert report["source_sha"] == "b" * 40 and not report["dirty"]
    assert len(report["output_fingerprints"]) == 1
    assert set(report["last_plan_output_hashes"]) == set(report["function_ids"])
    assert len(report["runs"]) == 2


@pytest.mark.parametrize("iterations", ["0", "11"])
def test_planning_benchmark_rejects_unbounded_iterations(monkeypatch, iterations):
    monkeypatch.setattr("sys.argv", ["benchmark", "--iterations", iterations])
    with pytest.raises(SystemExit) as exc:
        benchmark.main()
    assert exc.value.code == 2


def test_planning_benchmark_propagates_validation_failure(monkeypatch):
    monkeypatch.setattr("sys.argv", ["benchmark"])

    def invalid(identity):
        raise ValueError("invalid plan")

    monkeypatch.setattr(benchmark, "source_plan", invalid)
    with pytest.raises(ValueError, match="invalid plan"):
        benchmark.main()
