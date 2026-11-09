"""The tone-only cache fixture must not inherit a spoken closure constraint."""

import json
from copy import deepcopy

import pytest
from ocf_tools.semantic_dsp import load_profile, plan_program
from tools import benchmark_dsp_cache as benchmark

pytestmark = pytest.mark.unit


def test_tone_fixture_plans_without_mutating_approved_profile(monkeypatch):
    canonical = load_profile(benchmark.DSP_ID)
    before = deepcopy(canonical)
    monkeypatch.setattr(benchmark, "load_profile", lambda _: canonical)
    profile, document = benchmark.benchmark_inputs()
    assert canonical == before and canonical["transition_end_anchors"]
    assert profile["transition_end_anchors"] == {}
    assert profile["ignored_state_events"] == [] and profile["stage_backgrounds"] == {}
    for key in before.keys() - {
        "transition_end_anchors",
        "ignored_state_events",
        "stage_backgrounds",
    }:
        assert profile[key] == before[key]
    program = plan_program(document, [{"id": "transition", "at": 5, "end": 30}], 40, profile)
    assert program


def test_driver_reports_two_runs_without_inventing_listening_approval(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(benchmark, "work_path", lambda *args: tmp_path / "fixture")
    calls = []

    def render(document, timing, duration, profile, output):
        calls.append(output)
        assert duration == 40 and not profile["transition_end_anchors"]
        return {
            "output_sha256": "a" * 64,
            "selections": {
                "focus-10": {
                    "stem_cache": "hit" if len(calls) > 1 else "miss",
                    "stem_sha256": "b" * 64,
                },
            },
        }

    monkeypatch.setattr(benchmark, "render_program", render)
    benchmark.main()
    report = json.loads(capsys.readouterr().out)
    assert len(calls) == len(report["runs"]) == 2
    assert report["listening_approval"] is None
    assert report["runs"][0]["states"]["focus-10"]["stem_cache"] == "miss"
    assert report["runs"][1]["states"]["focus-10"]["stem_cache"] == "hit"
