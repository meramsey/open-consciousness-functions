import pytest
from ocf_tools.complete_session import build_complete_session_plan
from ocf_tools.session_overrides import resolve, verify_stage_limits
from ocf_tools.session_review import review_sessions
from ocf_tools.utils import OCFError


def test_explicit_ending_and_repetition_overrides_do_not_change_shared_defaults():
    standard = build_complete_session_plan("OCF-COG-006")
    awake = build_complete_session_plan(
        "OCF-COG-006",
        overrides={
            "sleep_continuation": False,
            "repetitions": {"programming": 1},
            "ending": "waking",
        },
    )
    assert "sleep20-body" not in {s["id"] for s in awake["stages"]}
    assert len(next(s for s in awake["stages"] if s["id"] == "focus11-body")["event_ids"]) == 1
    assert "return" in {s["id"] for s in awake["stages"]}
    sleep = build_complete_session_plan("OCF-SLP-005", overrides={"ending": "sleep"})
    assert "return" not in {s["id"] for s in sleep["stages"]}
    assert "function-closer" in {s["id"] for s in sleep["stages"]}
    assert build_complete_session_plan("OCF-COG-006")["template_plan"] == standard["template_plan"]
    assert not sleep["approval_state"]["release_ready"]


def test_precedence_conflicts_and_duration_failure_are_explicit():
    value, provenance = resolve(
        {"session_overrides": {"background_gain": 0.5, "repetitions": {"sleep": 1}}},
        {"background_gain": 0.25},
    )
    assert value["background_gain"] == 0.25 and provenance["background_gain"] == "cli"
    assert value["repetitions"]["sleep"] == 1
    with pytest.raises(OCFError, match="conflict"):
        resolve({}, {"ending": "sleep", "waking_return": True})
    with pytest.raises(OCFError, match="not compressed"):
        verify_stage_limits(
            {"sections": [{"id": "body", "timeline": [{"id": "speech"}]}]},
            [{"id": "speech", "at": 0, "end": 20}],
            {"body": 10},
        )


def test_representatives_use_actual_bindings_instead_of_category_heuristics():
    report = review_sessions(["OCF-COG-006", "OCF-BOD-002", "OCF-COG-007", "OCF-SLP-005"])
    assert len(report["functions"]) == 4
    assert all(row["body_passes"] == 4 and row["waking_return"] for row in report["functions"])
    assert (
        next(row for row in report["functions"] if row["function_id"] == "OCF-COG-007")["category"]
        == "cognition"
    )
    assert all(
        row["dsp"]["states"]["focus-10"]["preset"] == "OCF-BG-0012" for row in report["functions"]
    )
