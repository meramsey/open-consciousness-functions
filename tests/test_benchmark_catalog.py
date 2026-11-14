"""Benchmark reporting is tested without replacing the real catalog regressions."""

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from tools import benchmark_catalog as benchmark

pytestmark = pytest.mark.unit


@dataclass
class Entry:
    text: str


def test_catalog_benchmark_reports_population_fingerprint_and_timings(monkeypatch, capsys):
    fixture = SimpleNamespace(
        problems=[],
        packs={
            "en-US": SimpleNamespace(
                localized_functions={"OCF-TST-001": {"function_id": "OCF-TST-001"}},
                entries={"test.narration": Entry("Public fixture.")},
            )
        },
    )
    monkeypatch.setattr(benchmark, "LocaleCatalog", lambda: fixture)
    monkeypatch.setattr(
        benchmark.subprocess,
        "check_output",
        lambda argv, **kw: "a" * 40 if "rev-parse" in argv else "",
    )
    monkeypatch.setattr("sys.argv", ["benchmark", "--iterations", "2"])
    benchmark.main()
    data = json.loads(capsys.readouterr().out)
    assert data["source_sha"] == "a" * 40 and not data["dirty"]
    assert len(data["runs"]) == 2 and data["workers"] == 1
    assert len(data["semantic_fingerprints"]) == 1
    assert data["profiled_function_resource_scans"] == 0
    assert all(row["cpu_seconds"] >= 0 for row in data["runs"])
    before = benchmark.fingerprint(fixture)
    fixture.packs["en-US"].entries["test.narration"].text = "Changed fixture."
    assert benchmark.fingerprint(fixture) != before


@pytest.mark.parametrize("iterations", ["0", "21"])
def test_catalog_benchmark_rejects_unbounded_iterations(monkeypatch, iterations):
    monkeypatch.setattr("sys.argv", ["benchmark", "--iterations", iterations])
    with pytest.raises(SystemExit) as exc:
        benchmark.main()
    assert exc.value.code == 2


def test_catalog_benchmark_does_not_hide_catalog_failures(monkeypatch):
    monkeypatch.setattr("sys.argv", ["benchmark"])
    monkeypatch.setattr(
        benchmark, "LocaleCatalog", lambda: SimpleNamespace(problems=["invalid pack"])
    )
    with pytest.raises(RuntimeError, match="invalid pack"):
        benchmark.main()
