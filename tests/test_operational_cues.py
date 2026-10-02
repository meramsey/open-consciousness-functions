"""Operational cues announce their own semantic occurrence, not an illustration."""

import pytest
from ocf_tools.locale import iter_events
from ocf_tools.semantics import bind_document_cues
from ocf_tools.session import compose, load_template
from ocf_tools.utils import OCFError
from ocf_tools.validators import validate_narration_hygiene

OPERATIONAL = (
    "focus.ten.enter",
    "focus.ten.ready",
    "focus.eleven.open",
    "focus.eleven.ready",
    "focus.eleven.close",
    "session.complete",
)


@pytest.mark.parametrize("identity", OPERATIONAL)
def test_operational_cue_cannot_be_an_illustrative_sound(identity):
    doc = {
        "timeline": [
            {
                "id": "explain",
                "semantic": "preparation.cues.review",
                "at": "00:00.000",
                "auditory_cue": identity,
            }
        ]
    }
    # Even a disabled binding must be semantically valid: enabling a later
    # sound profile must not turn innocent explanation into a state signal.
    with pytest.raises(OCFError, match="operational.*semantic"):
        bind_document_cues(doc)


def test_invalid_operational_cue_is_a_validation_error():
    doc = {
        "timeline": [
            {
                "id": "explain",
                "semantic": "focus.eleven.learning",
                "at": "00:00.000",
                "auditory_cue": "focus.eleven.open",
            }
        ]
    }
    assert "semantic-cue-operation" in [
        issue.code for issue in validate_narration_hygiene(doc).errors
    ]


def test_all_preparation_operational_bindings_match_occurring_events():
    doc = compose(load_template("OCF-TPL-SESSION-PREP-LEARN-001"), {}, title="Cue contract")
    cues = bind_document_cues(doc)
    events = {event["id"]: event for event in iter_events(doc)}
    assert len(cues) == 7
    for cue in cues:
        assert cue["semantic"] == cue["identity"] == events[cue["event_id"]]["semantic"]
    for identifier in (
        "learn-working-state.learn",
        "learn-working-state.prime",
        "open.prepare",
        "close.prepare",
        "cue-review.review",
    ):
        assert "auditory_cue" not in events[identifier]


def test_repetition_or_rehearsal_label_does_not_bypass_operational_contract():
    doc = {
        "timeline": [
            {
                "id": "training",
                "semantic": "cue.rehearsal",
                "auditory_cue": "focus.eleven.open",
                "intentional_repeat": True,
            }
        ]
    }
    with pytest.raises(OCFError, match="operational.*semantic"):
        bind_document_cues(doc)
