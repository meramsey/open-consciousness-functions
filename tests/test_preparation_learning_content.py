"""Preparation Learning editorial integration: scope, ordering and previews.

These checks do not attempt to judge hypnotic effectiveness or prose quality.
"""

import importlib.util
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from ocf_tools.locale import LocaleCatalog, LocalizationError, iter_events, resolve_document
from ocf_tools.semantics import bind_document_cues
from ocf_tools.session import compose, load_template
from ocf_tools.timing import schedule_timeline
from ocf_tools.validators import validate_timed_transcript

spec = importlib.util.spec_from_file_location(
    "preparation_preview", REPO_ROOT / "scripts/tools/preview_preparation_learning.py"
)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


@pytest.mark.parametrize("optional", [False, True])
def test_complete_native_learning_composes_and_resolves_without_inline_english(optional):
    template = load_template("OCF-TPL-SESSION-PREP-LEARN-001")
    doc = compose(
        template, {}, title="Learning", enabled_stages=["affirmation", "tuning"] if optional else []
    )
    assert all("text" not in event for event in iter_events(doc))
    resolved = resolve_document(doc, "en-US")
    assert not validate_timed_transcript(resolved, Path("learning.yaml")).errors
    assert all(
        event.get("text", "").strip()
        for event in iter_events(resolved)
        if event.get("narration_required")
    )
    assert all(item["locale"] == "en-US" for item in resolved["narration"]["resolved"])


def test_preparation_does_not_teach_a_specific_function_or_activation_command():
    doc = preview.build_preview()["document"]
    assert "function_id" not in doc
    assert all("command" not in (event.get("variables") or {}) for event in iter_events(doc))
    assert not any("PLUS-" in event.get("text", "") for event in iter_events(doc))


def test_count_open_close_and_waking_completion_have_semantic_order():
    result = preview.build_preview()
    events = list(iter_events(result["document"]))
    by_id = {event["id"]: event for event in events}
    guided = [event["text"] for event in events if event["id"].startswith("focus-ten.count-")]
    assert [text.split(".", 1)[0] + "." for text in guided] == [
        "One.",
        "Two.",
        "Three.",
        "Four.",
        "Five.",
        "Six.",
        "Seven.",
        "Eight.",
        "Nine.",
    ]
    assert all(len(text.split()) > 5 for text in guided)
    assert by_id["focus-ten.enter"]["text"].startswith("Ten.")
    assert by_id["focus-ten.enter"]["text"].endswith("Focus Ten.")
    assert by_id["close.close"]["text"] == "Ten."
    assert by_id["open.open"]["text"] == "Eleven."
    assert by_id["open.transition"]["after"] == "open.open"
    assert by_id["open.ready"]["after"] == "open.transition"
    assert by_id["close.transition"]["after"] == "close.close"
    assert by_id["return.complete"]["dsp"]["state"] == "ordinary-waking"
    assert events[-1]["semantic"] == "session.complete"
    assert events[-1]["after"] == "return.complete"
    assert all(
        binding["binding"]["mode"] == "disabled"
        for binding in bind_document_cues(result["document"])
    )


def test_optional_affirmation_has_no_default_but_accepts_explicit_configuration():
    default = preview.build_preview()
    practice = next(
        event for event in iter_events(default["document"]) if event["id"] == "affirmation.practice"
    )
    assert "narration_key" not in practice and "text" not in practice
    configured = preview.build_preview(affirmation="I choose to explore this practice.")
    assert "I choose to explore this practice." in configured["listener"]
    assert configured["stats"]["spoken_words"] > default["stats"]["spoken_words"]


def test_learning_text_does_not_automatically_populate_routine_or_installation():
    for identifier in ("OCF-TPL-SESSION-PREP-ROUTINE-001", "OCF-TPL-SESSION-FUNCTION-INSTALL-001"):
        doc = compose(load_template(identifier), {}, title="Pending")
        assert not any(event.get("narration_key") for event in iter_events(doc))
        assert any(event.get("narration_required") for event in iter_events(doc))


def test_no_real_translation_is_generated_or_silently_substituted():
    doc = compose(load_template("OCF-TPL-SESSION-PREP-LEARN-001"), {}, title="Learning")
    with pytest.raises(LocalizationError):
        resolve_document(doc, "es")
    assert LocaleCatalog().require("es").get("preparation.learning.orientation.begin") is None


def test_three_automatic_learning_claims_are_removed_from_owned_shell():
    template = load_template("OCF-TPL-SESSION-LEARN-001")
    old = {
        "This function is being installed beneath conscious effort.",
        "Every word is received easily by your mind.",
        "All that you have absorbed is being integrated beneath awareness.",
    }
    assert not any(
        line.get("text") in old
        for section in template["sections"]
        for line in section.get("lines", [])
    )
    keys = {
        line.get("narration_key")
        for section in template["sections"]
        for line in section.get("lines", [])
    }
    assert {
        "function.learning.attend",
        "function.learning.rehearse",
        "function.learning.reflect",
    } <= keys


def test_review_views_are_fresh_and_do_not_invent_measured_speech():
    result = preview.build_preview()
    for name in ("listener", "developer"):
        assert (
            REPO_ROOT / f"docs/drafts/preparation-learning.en-US.{name}.md"
        ).read_text(encoding="utf-8") == result[name]
    assert "estimates" in result["developer"]
    assert "measured TTS" in result["developer"]
    assert result["stats"]["explicit_pause_s"] > 300
    assert result["stats"]["estimated_session_s"] > result["stats"]["estimated_speech_s"]


def test_editorial_word_budget_replaces_explanation_with_practice_time():
    result = preview.build_preview(include_optional=False)
    assert 1800 <= result["stats"]["spoken_words"] <= 2100
    # Phase 8A default: 384s of explicit pauses, ~1381s total at 140 words/min.
    # These are review-estimate bounds, not production timing requirements.
    assert result["stats"]["explicit_pause_s"] >= 540
    assert result["stats"]["estimated_session_s"] >= 0.95 * 1381
    catalog = LocaleCatalog()
    assert all(
        catalog.canonical.entries[event["narration_key"]].status == "reviewed"
        for event in iter_events(result["document"])
        if event.get("narration_key")
    )


def test_access_channel_context_and_unassigned_hypothetical_are_preserved():
    result = preview.build_preview(include_optional=False)
    text = result["listener"]
    assert "Access Channel" in text
    assert "Hearing a number in another setting needn't change anything." in text
    assert "demanding task" in text
    assert "leave the command open" in text
    assert "measurement of your brain" not in text


def test_composed_open_close_grammar_and_closing_line_are_explicit():
    doc = preview.build_preview(include_optional=False)["document"]
    events = {event["id"]: event for event in iter_events(doc)}
    for identifier, semantic, cue, key in (
        ("open.open", "focus.eleven.open", "focus.eleven.open", "focus.anchor.eleven"),
        ("open.ready", "focus.eleven.ready", "focus.eleven.ready", "focus.eleven.learning.ready"),
        ("close.close", "focus.eleven.close", "focus.eleven.close", "focus.anchor.ten"),
        ("close.ready", "focus.ten.ready", "focus.ten.ready", "focus.ten.learning.return.ready"),
    ):
        assert events[identifier]["semantic"] == semantic
        assert events[identifier]["auditory_cue"] == cue
        assert events[identifier]["narration_key"] == key
    assert events["open.open"]["after"] == "open.prepare"
    assert events["open.transition"]["after"] == "open.open"
    assert events["open.ready"]["after"] == "open.transition"
    assert events["recognize-eleven.recognize"]["after"] == "open.ready"
    assert events["close.close"]["after"] == "close.prepare"
    assert events["close.transition"]["after"] == "close.close"
    assert events["close.ready"]["after"] == "close.transition"
    assert events["recognize-return.recognize"]["after"] == "close.ready"
    assert events["open.transition"]["dsp"]["state"] == {"from": "focus-10", "to": "focus-11"}
    assert events["close.transition"]["dsp"]["state"] == {"from": "focus-11", "to": "focus-10"}
    assert events["close.prepare"]["text"].endswith("Give the settling its own time.")
    assert events["close.close"]["text"] == "Ten."
    assert events["close.close"]["narration_required"] is True

    # Text-review estimates prove the dependency arithmetic, not physical cue
    # playback. Cue + word/identification share their owning coordination event.
    durations = {
        identifier: len(preview.WORD.findall(event.get("text", ""))) * 60 / 140
        for identifier, event in events.items()
        if event.get("text")
    }
    schedule = {row["id"]: row for row in schedule_timeline(doc, durations)}
    for prefix in ("open", "close"):
        transition, ready = f"{prefix}.transition", f"{prefix}.ready"
        assert schedule[ready]["at"] == pytest.approx(
            schedule[transition]["at"] + durations[transition] + 25, abs=1e-5
        )
    assert schedule["close.close"]["at"] == pytest.approx(
        schedule["close.prepare"]["at"] + durations["close.prepare"] + 3, abs=1e-5
    )


def test_rc1_is_reviewed_without_approving_arbitrary_user_affirmation():
    template = load_template("OCF-TPL-SESSION-PREP-LEARN-001")
    assert template["name"] == "OCF Preparation Learning en-US RC1"
    assert template["content_status"] == "reviewed"
    assert template["version"] == "0.3.0"
    assert LocaleCatalog().canonical.entries["preparation.affirmation.words"].status == "draft"
