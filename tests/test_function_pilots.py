"""Pilot words are draft locale data; legacy identities and RC1 stay protected."""

import pytest
from ocf_tools.indexes import load_function_by_id
from ocf_tools.locale import iter_events, resolve_document
from ocf_tools.session import compose, load_template
from ocf_tools.timing import schedule_timeline


@pytest.mark.parametrize(
    "slug,function_id,command",
    [
        ("RELAX", "OCF-FND-004", "Plus Relax"),
        ("HEARING", "OCF-SEN-001", "Plus Hear More"),
        ("SLEEP-EASY", "OCF-SLP-005", "Plus Sleep Easy"),
    ],
)
def test_pilot_composition_command_ownership_and_pause_semantics(slug, function_id, command):
    template = load_template(f"OCF-TPL-SESSION-PILOT-{slug}-001")
    assert template["content_status"] == "draft"
    assert "REQUIRES HUMAN CONTENT REVIEW" in template["name"]
    doc = compose(template, {}, title=template["name"])
    assert doc["function_id"] == function_id
    assert all("text" not in event for event in iter_events(doc))
    resolved = resolve_document(doc, "en-US")
    events = list(iter_events(resolved))
    assert len(events) == 6 and any(command in event["text"] for event in events)
    owner = load_function_by_id(function_id)
    for event in iter_events(doc):
        variables = event.get("variables", {})
        if "function_name" in variables:
            assert variables["function_name"] == owner.canonical_name
        if "command" in variables:
            assert variables["command"] == command
    assert all(not event.get("dsp") and not event.get("auditory_cue") for event in events)
    schedule = schedule_timeline(resolved, {event["id"]: 10 for event in events})
    assert schedule[4]["at"] >= schedule[3]["at"] + 50  # speech plus40s rehearsal
    if slug == "SLEEP-EASY":
        record = load_function_by_id(function_id)
        assert (
            record.source_availability == "unavailable"
            and record.reimplementation_status == "planned"
        )
