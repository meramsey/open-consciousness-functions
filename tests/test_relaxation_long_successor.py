"""Approved words, real default bindings, pacing, and frozen-edition boundaries."""

import hashlib
import json
import re

import pytest
from ocf_tools import audio_defaults
from ocf_tools.complete_session import build_complete_session_plan
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog, iter_events, resolve_document
from ocf_tools.narration_pacing import plan_event_pacing, split_speech_units
from ocf_tools.paths import REPO_ROOT
from ocf_tools.session import compose, load_template
from ocf_tools.session_plans import source_plan
from ocf_tools.speech_cache import _synthesis_identity
from ocf_tools.transcript import resolve_timeline
from ocf_tools.utils import OCFError, yaml_safe_load

pytestmark = pytest.mark.integration
APPROVAL = REPO_ROOT / "function-content/editorial/relaxation-long-002.json"
KEY_PARTS = [
    "begin",
    "support",
    "face",
    "jaw-neck",
    "shoulders",
    "hands",
    "chest-breathing",
    "abdomen-lower-back",
    "hips-thighs",
    "lower-legs-feet",
    "whole-body-awareness",
]
COUNTS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def approval():
    return json.loads(APPROVAL.read_text())


def resolved(plan):
    return list(iter_events(resolve_document(plan["template_plan"], "en-US")))


def relaxation(events):
    return [e for e in events if e["id"].startswith("relaxation.") and e.get("text")]


def test_exact_approved_passage_and_anatomical_segmentation(approval):
    catalog = LocaleCatalog().with_revision(approval["id"], "en-US")
    keys = [f"hplus.shared.relaxation.{part}" for part in KEY_PARTS]
    assert approval["ordered_keys"] == keys
    entries = [catalog.resource(k, "en-US", domain="narration", fallback=False)[0] for k in keys]
    text = "\n\n".join(entry.text for entry in entries)
    # This independent fixed digest includes every punctuation mark, line break,
    # paragraph and word. Only resource boundary joining is deliberate.
    assert digest(text) == "2c5ece916a8dc35f0c99b8843244093040cd8670df5fbbdeccf552ac0dd75421"
    assert digest(text) == approval["assembled_text_sha256"]
    assert {e.key: digest(e.text) for e in entries} == approval["entry_text_sha256"]
    assert (
        re.findall(r"^(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)\.$", text, re.M) == COUNTS
    )
    assert [entry.text.splitlines()[0] for entry in entries[1:]] == [f"{c}." for c in COUNTS]
    assert [len(e.text.split("\n\n")) for e in entries] == [2] + [1] * 9 + [2]
    for entry in entries:
        assert entry.status == "reviewed" and entry.version == "2.0.0"
        assert len(entry.timing["pacing_units"]) == len(split_speech_units(entry.text))
    assert text.endswith("as we continue into the next part of the exercise.")
    assert all(word not in text.lower() for word in ("brain", "sleep"))


@pytest.mark.parametrize("owner", ["OCF-FND-002", "OCF-SEN-001"])
def test_normal_function_default_consumes_long_successor(owner, approval):
    # This checkpoint is now an explicit historical edition; v3 owns the
    # current default and deliberately changes other shared stages.
    plan = build_complete_session_plan(owner, template="OCF-TPL-SESSION-HPLUS-LOCKED-006")
    assert plan["template"]["id"] == "OCF-TPL-SESSION-HPLUS-LOCKED-006"
    assert plan["template_plan"]["narration_revision"] == approval["id"]
    events = resolved(plan)
    body = relaxation(events)
    assert [e["id"] for e in body] == [f"relaxation.{part}" for part in KEY_PARTS]
    assert digest("\n\n".join(e["text"] for e in body)) == approval["assembled_text_sha256"]
    old = build_complete_session_plan(owner, template="OCF-TPL-SESSION-HPLUS-LOCKED-005")
    # All unrelated spoken text and event policy is identical; downstream absolute
    # timing is intentionally not frozen to the old speech duration.
    before = {e["id"]: e for e in resolved(old) if not e["id"].startswith("relaxation.")}
    after = {e["id"]: e for e in events if not e["id"].startswith("relaxation.")}
    assert before == after
    for field in (
        "state_directives",
        "effective_state_directives",
        "ignored_state_directives",
        "resolved_dsp_profile",
    ):
        assert plan[field] == old[field]
    assert sum(e.get("semantic") == "function.instruction" for e in events) == 4
    assert plan["resolved_pacing_profile"]["underlay"] == old["resolved_pacing_profile"]["underlay"]


def test_every_active_shared_consumer_has_explicit_successor_binding():
    records = load_all_functions()
    assert len(records) == 58
    for record in records:
        binding = record.data["content"]["bindings"]
        assert binding["default_session_template"] == audio_defaults.TEMPLATE_ID
        assert {"OCF-TPL-SESSION-HPLUS-LOCKED-005", audio_defaults.TEMPLATE_ID} <= set(
            binding["session_templates"]
        )


def test_complete_canonical_text_map_and_previous_approvals_unchanged(approval):
    catalog = LocaleCatalog()
    actual = {k: digest(v.text) for k, v in catalog.require("en-US").entries.items()}
    assert actual == approval["unchanged_canonical_entry_text_sha256"]
    for name, expected in approval["frozen_file_sha256"].items():
        assert hashlib.sha256((REPO_ROOT / name).read_bytes()).hexdigest() == expected, name
    assert approval["human_listening_approval"] is None and approval["release_ready"] is False
    # Earlier historical locks intentionally predate other approved function
    # successors. Their immutable bytes are checked above, not re-baselined.
    assert (
        hashlib.sha256(
            (REPO_ROOT / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-016.json").read_bytes()
        ).hexdigest()
        == "8677dbaefde4111ffdb8fb92a876c15e5d7d5b73d4cbbd3048a1e05cf0553bf4"
    )
    assert (
        hashlib.sha256(
            (REPO_ROOT / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-017.json").read_bytes()
        ).hexdigest()
        == "f150209ee5a37d6ceda2fc7851101dc2ae1e0ee8e99a2b56c1b42813e00b5f6d"
    )
    # V3 deliberately supersedes dependencies recorded by 016/017. Their
    # immutable receipts remain historical; the validator must still reject
    # applying them to current inputs, rather than rewriting old lock bytes.
    for identity in ("OCF-AUDIO-DEFAULTS-HPLUS-016", "OCF-AUDIO-DEFAULTS-HPLUS-017"):
        with pytest.raises(OCFError, match="shared audio defaults lock is stale"):
            audio_defaults.check_lock(REPO_ROOT / "audio/defaults" / f"{identity}.json")
    audio_defaults.check_lock(REPO_ROOT / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-015.json")
    audio_defaults.check_lock()


def test_historical_templates_and_rc1_preserve_transitive_resolved_words(approval):
    slots = {
        slot: f"hplus.function.ocf-sen-001.{slot.replace('_', '-')}"
        for slot in ("opener", "function_body", "closer")
    }
    for identity, expected in approval["frozen_template_event_text_sha256"].items():
        doc = compose(
            load_template(identity),
            {},
            title="Baseline",
            function_id="OCF-SEN-001",
            slot_keys={} if identity.endswith("PREP-LEARN-001") else slots,
        )
        actual = {
            e["id"]: digest(e.get("text", "")) for e in iter_events(resolve_document(doc, "en-US"))
        }
        assert actual == expected, identity


def test_successor_section_and_pause_policy_are_strictly_scoped():
    old = load_template("OCF-TPL-SESSION-HPLUS-LOCKED-005")
    new = load_template("OCF-TPL-SESSION-HPLUS-LOCKED-006")
    assert [s for s in old["sections"] if s["id"] != "relaxation"] == [
        s for s in new["sections"] if s["id"] != "relaxation"
    ]
    plan = build_complete_session_plan("OCF-SEN-001", template="OCF-TPL-SESSION-HPLUS-LOCKED-006")
    previous = build_complete_session_plan("OCF-SEN-001", template=old["id"])
    for field in (
        "pauses",
        "transitions",
        "estimate",
        "voice_profile_id",
        "repetitions",
        "duration_preference",
    ):
        assert plan["resolved_pacing_profile"][field] == previous["resolved_pacing_profile"][field]
    events = resolved(plan)
    for event in relaxation(events):
        paced = plan_event_pacing(plan["template_plan"], event)
        assert paced and paced["rate_scale"] == 0.88
        assert " ".join(u["text"] for u in paced["units"]) == " ".join(event["text"].split())
        # The last unit uses only the existing event hold, not landing+hold.
        assert paced["units"][-1]["pause_inside_event"] is False
        assert paced["units"][-1]["pause_after_s"] == event["timing"]["pause_after"]
        assert "preferred_duration" not in event["timing"]
    hold = next(e for e in events if e["id"] == "relaxation.whole")
    assert hold["timing"]["pause_after"] == 30
    assert (
        next(e for e in events if e["id"] == "body-comfort.breathing-hold")["timing"]["pause_after"]
        == 20
    )
    assert (
        next(e for e in events if e["id"] == "transmutation-box.place")["timing"]["pause_after"]
        == 20
    )


@pytest.mark.parametrize("choice", [None, "none", "Gateway", "SyncCreation", "OCF", "custom"])
def test_relaxation_revision_preserves_existing_affirmation_choices_and_explicit_enable(choice):
    slots = {
        "opener": "Synthetic opener.",
        "function_body": "Synthetic body.",
        "closer": "Synthetic closer.",
    }
    if choice == "custom":
        slots["affirmation"] = "Synthetic explicit custom text."
    selections = []
    for identity in ("OCF-TPL-SESSION-HPLUS-LOCKED-005", "OCF-TPL-SESSION-HPLUS-LOCKED-006"):
        doc = compose(
            load_template(identity),
            slots,
            title="Fixture",
            enabled_stages=["affirmation"],
            affirmation=choice,
        )
        selections.append([e for e in iter_events(doc) if e["id"].startswith("affirmation.")])
        if choice is None:
            assert "affirmation_selection" not in doc
        else:
            assert doc["affirmation_selection"] == choice
    assert selections[0] == selections[1]
    assert len(selections[1]) == (0 if choice == "none" else 3)


def test_strict_revision_locale_and_duplicate_keys_are_not_bypassed(approval):
    with pytest.raises(OCFError):
        LocaleCatalog().with_revision(approval["id"], "es")
    with pytest.raises(Exception, match="duplicate"):
        yaml_safe_load("locale: en-US\nlocale: es\n")


def test_text_addressed_cache_cannot_reuse_old_relaxation(monkeypatch):
    monkeypatch.setattr("ocf_tools.speech_cache.voice_identity", lambda spec: {"fixture": True})
    old = LocaleCatalog()
    new = old.with_revision("OCF-RELAXATION-LONG-002", "en-US")
    for part in ("begin", "face", "shoulders", "hands"):
        key = f"hplus.shared.relaxation.{part}"
        a = old.resource(key, "en-US", domain="narration", fallback=False)[0]
        b = new.resource(key, "en-US", domain="narration", fallback=False)[0]
        assert a.text != b.text and a.version != b.version
        assert (
            _synthesis_identity({"locale": "en-US"}, a.text)[1]
            != _synthesis_identity({"locale": "en-US"}, b.text)[1]
        )


def test_predecessor_landing_pacing_remains_available_explicitly():
    plan = build_complete_session_plan("OCF-SLP-005", template="OCF-TPL-SESSION-HPLUS-LOCKED-005")
    torso = next(
        item
        for item in plan["narration_pacing_plan"]
        if item["narration_key"] == "hplus.shared.relaxation.torso"
    )
    landings = [unit for unit in torso["units"] if unit["text"] == "Sleep."]
    assert [unit["kind"] for unit in landings] == ["landing"] * 4
    assert [unit["pause_after_s"] for unit in landings] == [5.0, 5.0, 5.0, 6.0]


def test_generated_shared_plan_fingerprints_selected_revision(approval):
    _, shared, _ = source_plan("OCF-FND-002")
    resources = {row["key"]: row for row in shared["resources"]}
    for key, expected in approval["entry_text_sha256"].items():
        assert resources[key]["text_sha256"] == expected
        assert resources[key]["version"] == "2.0.0"
    assert not set(approval["active_key_removals"]) & resources.keys()


def test_pronunciation_preflight_retains_revision_with_a_base_catalog():
    from ocf_tools.voice import _pronunciation_hints

    plan = build_complete_session_plan("OCF-SEN-001")
    doc = resolve_document(plan["template_plan"], "en-US")
    # Renderer/cache callers may supply their general catalog; pronunciation
    # must consult the selected revision just like text and integrity do.
    assert isinstance(_pronunciation_hints(doc, "en-US", LocaleCatalog(), "piper"), dict)


def test_speech_relative_timeline_never_caps_new_long_speech():
    plan = build_complete_session_plan("OCF-SEN-001", template="OCF-TPL-SESSION-HPLUS-LOCKED-006")
    doc = resolve_document(plan["template_plan"], "en-US")
    events = list(iter_events(doc))
    # Synthetic long measurements deliberately exceed the old session target.
    # These are test inputs, not a new silence or delivery-rate policy.
    durations = {e["id"]: 300.0 if e.get("text") else 0.0 for e in events}
    timed, problems = resolve_timeline(doc, speech_durations=durations)
    assert not problems
    starts = {e.id: e.at for e in timed}
    by_id = {e["id"]: e for e in events}
    for event in events:
        if event["id"].startswith("relaxation.") and event.get("after"):
            previous = event["after"]
            assert starts[event["id"]] == pytest.approx(
                starts[previous]
                + durations[previous]
                + by_id[previous].get("timing", {}).get("pause_after", 0)
            )
    assert starts["focus-ten.learn"] > starts["relaxation.whole-body-awareness"] + 300
    assert starts["session-complete.signal"] > 2700


@pytest.mark.parametrize("owner", ["OCF-FND-002", "OCF-SEN-001"])
def test_cli_normal_complete_route_selects_long_form(owner, approval, capsys, monkeypatch):
    from ocf_tools import cli, narration_first

    # Only optional backend discovery is isolated; selection/composition and the
    # CLI complete-session route run normally, without a template override.
    monkeypatch.setattr(
        narration_first,
        "_voice_profile",
        lambda query, locale, catalog: (
            {
                "id": "OCF-VOICE-0003",
                "slug": "fixture",
                "name": "Fixture",
                "backend": "piper",
                "piper_length_scale": 1.12,
            },
            {"name": "piper", "language": "en_US", "wpm": None},
        ),
    )
    assert cli.main(["audio", "render", owner, "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True
    plan = report["session_plan"]
    assert plan["template"]["id"] == audio_defaults.TEMPLATE_ID
    assert (
        digest("\n\n".join(e["text"] for e in relaxation(resolved(plan))))
        == approval["assembled_text_sha256"]
    )
