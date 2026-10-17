import json

import pytest
from ocf_tools import editorial_queue as review
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "choice,status",
    [
        ("approve", "approved-awaiting-scoped-implementation"),
        ("custom", "approved-awaiting-scoped-implementation"),
        ("keep", "keep-current-pair-recorded"),
        ("skip", "deferred"),
        ("context", "pending"),
    ],
)
def test_explicit_decision_retains_verbatim_text_and_resumes(tmp_path, monkeypatch, choice, status):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(review, "fingerprint", lambda owner: "fixture-sha")
    queue = {
        "position": 0,
        "items": [
            {
                "function_id": "OCF-BOD-003",
                "status": "pending",
                "decisions": [],
                "source_sha256": "fixture-sha",
            },
            {
                "function_id": "OCF-BOD-006",
                "status": "pending",
                "decisions": [],
                "source_sha256": "fixture-sha",
            },
        ],
    }
    response = "Use MY-CUE, exactly!"
    row = review.decide(
        queue,
        "OCF-BOD-003",
        choice,
        response,
        title="My Title",
        display_cue="MY-CUE",
        spoken_cue="My Cue",
    )
    assert row["status"] == status and row["decisions"][-1]["user_text"] == response
    path = review.save(queue)
    assert review.load_or_create(path) == queue
    assert review.next_item(queue)["function_id"] == (
        "OCF-BOD-006" if choice in {"keep", "skip"} else "OCF-BOD-003"
    )


@pytest.mark.parametrize(
    "choice,text,owner",
    [
        ("approve", "", "current"),
        ("automatic", "Yes", "current"),
        ("approve", "Yes", "different"),
        ("custom", "Custom", "current"),
    ],
)
def test_missing_ambiguous_or_out_of_turn_decisions_do_not_mutate(choice, text, owner):
    queue = {
        "items": [
            {
                "function_id": "current",
                "status": "pending",
                "decisions": [],
                "source_sha256": "fixture-sha",
            }
        ]
    }
    before = json.dumps(queue)
    with pytest.raises(OCFError):
        review.decide(queue, owner, choice, text, source_fingerprint=lambda owner: "fixture-sha")
    assert json.dumps(queue) == before


def test_resume_and_decision_reject_source_drift_without_erasing_history(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    queue = {
        "items": [
            {
                "function_id": "fixture",
                "status": "pending",
                "decisions": [{"choice": "context", "user_text": "Show exact context"}],
                "source_sha256": "old",
            }
        ]
    }
    path = review.save(queue)
    original = path.read_bytes()
    with pytest.raises(OCFError, match="source changed"):
        review.load_or_create(path, source_fingerprint=lambda owner: "changed")
    before = json.dumps(queue)
    with pytest.raises(OCFError, match="source changed"):
        review.decide(
            queue, "fixture", "approve", "Yes", source_fingerprint=lambda owner: "changed"
        )
    assert json.dumps(queue) == before and path.read_bytes() == original
