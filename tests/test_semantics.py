"""Semantic stage composition and auditory bindings, independent of narration."""

from copy import deepcopy

import pytest
from ocf_tools.locale import LocalizationError, iter_events, resolve_document
from ocf_tools.semantics import (
    bind_document_cues,
    load_cue_profile,
    load_stage,
    stage_events,
)
from ocf_tools.session import compose, load_template
from ocf_tools.transcript import resolve_timeline
from ocf_tools.utils import OCFError
from ocf_tools.validators import _load_schema, validate_against_schema


def preparation(**options):
    return compose(load_template("OCF-TPL-SESSION-PREP-LEARN-001"), {}, title="Architecture", **options)


def test_learning_stage_order_and_optional_composition():
    doc = preparation()
    assert [section["id"] for section in doc["sections"]] == [
        "orientation", "setting-aside", "relaxation", "focus-ten", "recognize-ten",
        "learn-working-state", "open", "recognize-eleven", "function-concept",
        "command-learning", "close", "recognize-return", "cue-review", "return",
    ]
    enabled = preparation(enabled_stages=["affirmation", "tuning"])
    assert [section["id"] for section in enabled["sections"]][1:5] == [
        "setting-aside", "affirmation", "tuning", "relaxation",
    ]
    assert not resolve_timeline(doc)[1]
    assert not resolve_timeline(enabled)[1]
    with pytest.raises(OCFError, match="unknown optional"):
        preparation(enabled_stages=["typo"])


def test_stage_instances_keep_unique_ids_and_version_provenance():
    doc = preparation()
    ids = [event["id"] for event in iter_events(doc)]
    assert len(ids) == len(set(ids))
    assert "recognize-ten.recognize" in ids and "recognize-return.recognize" in ids
    assert doc["stages"][0] == {"id": "OCF-TPL-STAGE-ORIENTATION-001", "version": "0.2.0", "instance": "orientation"}


def test_locale_resolution_cannot_change_semantics_dsp_or_cues():
    doc = preparation()
    english = resolve_document(doc, "en-US")
    assert [{key: value for key, value in event.items() if key != "text"} for event in iter_events(english)] == list(iter_events(doc))
    assert all("text" not in event for event in iter_events(doc))
    # The new content is en-US only. Missing real translations must remain
    # a strict failure, not be manufactured to keep an old demo assertion green.
    with pytest.raises(LocalizationError, match="required spoken narration"):
        resolve_document(doc, "es")


def test_opening_coordinates_narration_then_dsp_then_ready():
    events = stage_events(load_stage("OCF-TPL-STAGE-FOCUS-ELEVEN-OPEN-001"), "open")
    assert [event["semantic"] for event in events] == [
        "focus.eleven.open.prepare", "focus.eleven.open", "focus.eleven.transition.open", "focus.eleven.ready",
    ]
    assert events[2]["after"] == events[1]["id"]
    assert events[2]["dsp"]["state"] == {"from": "focus-10", "to": "focus-11"}
    assert events[3]["after"] == events[2]["id"]
    assert events[3]["auditory_cue"] == "focus.eleven.ready"


def test_cue_profile_replacement_does_not_modify_session_or_subtitle_id():
    doc = {"timeline": [{"id": "e", "at": "00:00.000", "semantic": "focus.eleven.open",
                         "auditory_cue": "focus.eleven.open", "cue_id": "vtt-source-7"}]}
    before = deepcopy(doc)
    disabled = bind_document_cues(doc)
    profile = load_cue_profile()
    profile["bindings"]["focus.eleven.open"] = {"mode": "generator", "generator": "future-design", "license": "TBD"}
    generated = bind_document_cues(doc, profile)
    assert disabled[0]["binding"]["mode"] == "disabled"
    assert generated[0]["binding"]["generator"] == "future-design"
    assert doc == before


def test_future_semantic_identity_needs_no_schema_redesign():
    doc = {"schema_version": "1.0", "title": "Future", "timeline": [
        {"id": "new", "at": "00:00.000", "semantic": "community.new-practice.ready"},
    ]}
    assert not validate_against_schema(doc, _load_schema("timed-transcript.schema.json"))


def test_unbound_auditory_identity_is_visible_before_render():
    with pytest.raises(OCFError, match="unbound"):
        bind_document_cues({"timeline": [{"id": "e", "auditory_cue": "community.new.ready"}]})


def test_bad_local_stage_anchor_is_not_guessed():
    stage = load_stage("OCF-TPL-STAGE-FOCUS-TEN-001")
    stage["events"][1]["after"] = "absent"
    with pytest.raises(OCFError, match="unknown local anchor"):
        stage_events(stage, "ten")


def test_routine_and_installation_share_stages_without_learning_lecture():
    routine = compose(load_template("OCF-TPL-SESSION-PREP-ROUTINE-001"), {}, title="Routine")
    install = compose(load_template("OCF-TPL-SESSION-FUNCTION-INSTALL-001"), {}, title="Function")
    assert len(routine["stages"]) < len(preparation()["stages"])
    assert "learn-working-state" not in [section["id"] for section in routine["sections"]]
    assert "OCF-TPL-STAGE-COMMAND-LEARNING-001" in [stage["id"] for stage in install["stages"]]
    assert "sleep20" not in [section["id"] for section in install["sections"]]
    returning = compose(load_template("OCF-TPL-SESSION-FUNCTION-INSTALL-001"), {}, title="Return", enabled_stages=["return"])
    assert returning["sections"][-1]["id"] == "return"
