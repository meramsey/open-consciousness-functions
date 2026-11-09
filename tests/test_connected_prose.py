"""Connected delivery preserves words and explicit semantic waits."""

from copy import deepcopy

import pytest
from ocf_tools.learning_session import plan
from ocf_tools.locale import iter_events
from ocf_tools.narration_pacing import plan_event_pacing

pytestmark = pytest.mark.unit


def test_connected_learning_keeps_words_practice_and_counts():
    old = plan(native_speed=True)
    new = plan(native_speed=True, pacing_profile="OCF-PACING-CONNECTED-LEARNING-001")
    assert new["practice_seconds"] == old["practice_seconds"] == 510
    before = list(iter_events(old["document"]))
    after = list(iter_events(new["document"]))
    assert before == after
    changed = 0
    for event in after:
        a = plan_event_pacing(old["document"], event)
        b = plan_event_pacing(new["document"], event)
        if a is None:
            assert b is None
            continue
        assert " ".join(u["text"] for u in a["units"]) == " ".join(u["text"] for u in b["units"])
        assert a["units"][-1]["pause_after_s"] == b["units"][-1]["pause_after_s"]
        counts = {"count", "countdown", "final_countdown"}
        assert [u for u in a["units"] if u["kind"] in counts] == [
            {k: v for k, v in u.items() if k != "source_unit_indexes"}
            for u in b["units"]
            if u["kind"] in counts
        ]
        changed += len(b["units"]) < len(a["units"])
        if event["id"] == "transmutation-box.place":
            assert any(
                "Do this now. I will wait while you do this." in u["text"] for u in b["units"]
            )
    assert changed > 5


def test_paragraph_and_count_boundaries_are_retained():
    doc = {
        "narration_pacing": {
            "entries": {"test.text": "test"},
            "profiles": {
                "test": {
                    "rate_scale": 1,
                    "default_unit": "sentence",
                    "group_prose": True,
                    "pauses": {"sentence": 2, "paragraph": 4, "count": 6},
                }
            },
        }
    }
    event = {
        "narration_key": "test.text",
        "text": "One. Settle. Rest.\n\nBreathe. Stay.",
        "timing": {
            "narration_pacing_units": ["count", "sentence", "sentence", "sentence", "sentence"],
            "pause_after": 20,
        },
    }
    original = deepcopy(event)
    units = plan_event_pacing(doc, event)["units"]
    assert [u["text"] for u in units] == ["One.", "Settle. Rest.", "Breathe. Stay."]
    assert [u["pause_after_s"] for u in units] == [6, 4, 20]
    assert [u["source_unit_indexes"] for u in units] == [[0], [1, 2], [3, 4]]
    assert event == original
