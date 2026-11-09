import copy
import hashlib
import itertools
import json
import re

import pytest
from ocf_tools import audio_defaults, semantic_dsp
from ocf_tools.complete_session import build_complete_session_plan
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog, iter_events, resolve_document
from ocf_tools.narration_pacing import plan_event_pacing
from ocf_tools.paths import REPO_ROOT
from ocf_tools.session import compose, load_template
from ocf_tools.session_pacing_audit import audit_shared_v3
from ocf_tools.transcript import resolve_timeline
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration
REVISION = "OCF-SHARED-SESSION-003"
ROUTINE = "OCF-TPL-SESSION-HPLUS-LOCKED-007"
LEARNING = "OCF-TPL-SESSION-PREP-LEARN-002"
NUMBERS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def struct_sha(data):
    return sha(json.dumps(data, sort_keys=True, ensure_ascii=False))


@pytest.fixture(scope="module")
def approval():
    return json.loads(
        (REPO_ROOT / "function-content/editorial/shared-session-v3-001.json").read_text()
    )


def routine(owner="OCF-SEN-001", **kwargs):
    plan = build_complete_session_plan(owner, **kwargs)
    return plan, resolve_document(plan["template_plan"], "en-US")


def lesson(**kwargs):
    return resolve_document(
        compose(load_template(LEARNING), {}, title="Reviewed learning", locale="en-US", **kwargs),
        "en-US",
    )


def synthetic_timeline(doc):
    """Planning durations, not synthesis/listening evidence; actual anchor resolver."""
    events = list(iter_events(doc))
    durations, units = {}, {}
    for event in events:
        paced = plan_event_pacing(doc, event)
        rows, cursor = [], 0.0
        if paced:
            for unit in paced["units"]:
                length = max(0.1, len(unit["text"].split()) * 60 / 160 / unit["rate_scale"])
                rows.append(
                    {
                        "text": unit["text"],
                        "start_seconds": cursor,
                        "end_seconds": cursor + length,
                        "audible_end_seconds": cursor + length - 0.01,
                    }
                )
                cursor += length + (unit["pause_after_s"] if unit["pause_inside_event"] else 0)
        elif event.get("text"):
            cursor = len(event["text"].split()) * 60 / 160
            rows = [
                {
                    "text": event["text"],
                    "start_seconds": 0,
                    "end_seconds": cursor,
                    "audible_end_seconds": cursor - 0.01,
                }
            ]
        durations[event["id"]] = cursor
        units[event["id"]] = rows
    timed, problems = resolve_timeline(doc, speech_durations=durations)
    assert not problems
    rows = []
    for event in timed:
        assert event.at is not None
        spoken = [
            {
                **unit,
                **{
                    key: unit[key] + event.at
                    for key in ("start_seconds", "end_seconds", "audible_end_seconds")
                },
            }
            for unit in units[event.id]
        ]
        rows.append(
            {
                "id": event.id,
                "at": event.at,
                "duration": durations[event.id],
                "end": event.at + durations[event.id],
                "spoken_units": spoken,
                "spoken_text": event.text,
            }
        )
    raw = {e["id"]: e for e in events}
    total = max(
        r["at"]
        + max(r["duration"], raw[r["id"]].get("dsp", {}).get("transition_s", 0))
        + raw[r["id"]].get("timing", {}).get("pause_after", 0)
        for r in rows
    )
    return rows, total


def test_all_appendix_blocks_match_frozen_exact_resolved_and_raw_hashes(approval):
    catalog = LocaleCatalog().with_revision(REVISION, "en-US")
    expected = {k: row["resolved_sha256"] for k, row in approval["blocks"].items()}
    assert (
        sha(json.dumps(expected, sort_keys=True))
        == "b250e380b305d572ad009dff67566a12eb5a6cd76ea4d6e39675e799f6ed0d19"
    )
    for row in approval["blocks"].values():
        text = "\n\n".join(
            catalog.resource(k, "en-US", domain="narration", fallback=False)[0].text
            for k in row["ordered_keys"]
        )
        assert sha(text) == row["resolved_sha256"]
    for key, expected in approval["entry_hashes"].items():
        entry = catalog.resource(key, "en-US", domain="narration", fallback=False)[0]
        assert sha(entry.text) == expected["resolved_sha256"]
        assert (
            sha(entry.raw_template if entry.raw_template is not None else entry.text)
            == expected["raw_sha256"]
        )
        assert entry.status == "reviewed" and entry.version == expected["version"]
    assert approval["listening_approval"] is None and approval["release_ready"] is False
    assert all(
        not r["publication_clearance"] and not r["authenticated_source"]
        for r in approval["supplied_presets"].values()
    )


@pytest.mark.parametrize("owner", ["OCF-FND-002", "OCF-SEN-001"])
def test_normal_default_selects_single_induction_and_exact_four_pass_sequence(owner, approval):
    plan, doc = routine(owner)
    assert plan["template"]["id"] == audio_defaults.TEMPLATE_ID == ROUTINE
    assert doc["narration_revision"] == REVISION
    events = list(iter_events(doc))
    by_id = {e["id"]: e for e in events}
    scan = [e for e in events if e["id"].startswith("relaxation.")]
    text = "\n\n".join(e["text"] for e in scan)
    assert sha(text) == approval["blocks"]["06"]["resolved_sha256"]
    assert (
        re.findall(r"^(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)\.$", text, re.M) == NUMBERS
    )
    assert "relaxation.whole" not in by_id and "focus-ten.learn" not in by_id
    assert not any(e["id"].startswith("focus-ten.count-") for e in events)
    assert not by_id["focus-ten.enter"].get("text")
    assert by_id["focus-ten.ready"]["timing"]["pause_after"] == 40
    assert by_id["close.close"]["text"].splitlines().count("Ten.") == 4
    assert by_id["open.open"]["text"] == "Eleven."
    assert by_id["close.confirmed"]["text"].startswith("Your Access Channel is now closed.")
    assert by_id["close.ready"]["timing"]["pause_after"] == 0
    assert (
        by_id["focus20-enter.calm"]["text"]
        == "Relax and feel calm and serene in the twentieth state."
    )
    assert [
        u["text"]
        for p in plan["narration_pacing_plan"]
        if p["event_id"] == "focus20-enter.enter"
        for u in p["units"]
        if u["kind"] == "countdown"
    ] == [
        c + "."
        for c in [
            "Ten",
            "Eleven",
            "Twelve",
            "Thirteen",
            "Fourteen",
            "Fifteen",
            "Sixteen",
            "Seventeen",
            "Eighteen",
            "Nineteen",
            "Twenty",
            "Twenty",
        ]
    ]
    assert not any(e.get("text") for e in events if e["id"].startswith("focus20-close."))
    bodies = [e for e in events if e.get("slot_ref") == "function_body"]
    assert [e["id"] for e in bodies] == [
        "focus11-body.pass-1",
        "focus11-body.pass-2",
        "sleep20-body.pass-1",
        "sleep20-body.pass-2",
    ]
    assert len({e["narration_key"] for e in bodies}) == len({e["text"] for e in bodies}) == 1
    assert (
        sum(e.get("slot_ref") == "opener" for e in events)
        == sum(e.get("slot_ref") == "closer" for e in events)
        == 1
    )
    ids = list(by_id)
    assert (
        ids.index("close.close")
        < ids.index("close.transition")
        < ids.index("close.confirmed")
        < ids.index("close.ready")
    )
    assert (
        ids.index("focus20-enter.enter")
        < ids.index("focus20-enter.calm")
        < ids.index("sleep20-body.pass-1")
    )
    assert not any(e["id"].startswith("open-2.") or e["id"].startswith("learning-") for e in events)


def test_whole_unaffected_map_commands_bindings_and_frozen_editions(approval):
    catalog = LocaleCatalog()
    declared = catalog.require("en-US").manifest["resources"]
    assert len([r["file"] for r in declared]) == len({r["file"] for r in declared})
    long_revision = catalog.with_revision("OCF-RELAXATION-LONG-002", "en-US")
    session_revision = catalog.with_revision(REVISION, "en-US")
    for key in approval["blocks"]["06"]["ordered_keys"]:
        assert (
            long_revision.resource(key, "en-US", domain="narration", fallback=False)[0].text
            == session_revision.resource(key, "en-US", domain="narration", fallback=False)[0].text
        )
    actual = {
        k: {
            "raw_sha256": sha(v.text),
            "resolved_sha256": sha(
                catalog.resource(k, "en-US", domain=v.domain, fallback=False)[0].text
            ),
        }
        for k, v in catalog.require("en-US").entries.items()
    }
    assert actual == approval["unchanged_canonical_entries"]
    for record in load_all_functions():
        data = copy.deepcopy(record.data)
        binding = data["content"].pop("bindings")
        assert (
            struct_sha(data)
            == approval["unchanged_function_records_without_bindings_sha256"][record.id]
        )
        assert binding.pop("default_session_template") == ROUTINE
        assert binding.pop("session_templates") == sorted(
            set(approval["previous_session_templates"][record.id]) | {ROUTINE}
        )
        assert struct_sha(binding) == approval["unchanged_binding_payload_sha256"][record.id]
    for name, expected in approval["frozen_file_sha256"].items():
        assert hashlib.sha256((REPO_ROOT / name).read_bytes()).hexdigest() == expected, name
    for owner, expected in approval["frozen_resolved_event_hashes"].items():
        old = build_complete_session_plan(owner, template="OCF-TPL-SESSION-HPLUS-LOCKED-006")
        events = iter_events(resolve_document(old["template_plan"], "en-US"))
        assert {e["id"]: sha(e.get("text", "")) for e in events} == expected
    rc1 = resolve_document(
        compose(load_template("OCF-TPL-SESSION-PREP-LEARN-001"), {}, title="Frozen RC1"), "en-US"
    )
    assert {e["id"]: sha(e.get("text", "")) for e in iter_events(rc1)} == approval[
        "rc1_event_text_sha256"
    ]
    assert audio_defaults.check_lock()["id"] == "OCF-AUDIO-DEFAULTS-HPLUS-018"


def test_long_form_revision_is_an_explicit_manifest_alias_without_duplicate_resource():
    pack = LocaleCatalog().require("en-US")
    rows = pack.manifest["resources"]
    assert len([row["file"] for row in rows]) == len({row["file"] for row in rows})
    aliases = [row for row in rows if "OCF-RELAXATION-LONG-002" in row.get("revision_aliases", [])]
    assert len(aliases) == 1 and aliases[0]["revision"] == REVISION
    first = LocaleCatalog().with_revision("OCF-RELAXATION-LONG-002", "en-US")
    v3 = LocaleCatalog().with_revision(REVISION, "en-US")
    for key in json.loads(
        (REPO_ROOT / "function-content/editorial/relaxation-long-002.json").read_text()
    )["ordered_keys"]:
        assert (
            first.resource(key, "en-US", domain="narration", fallback=False)[0].text
            == v3.resource(key, "en-US", domain="narration", fallback=False)[0].text
        )


@pytest.mark.parametrize(
    "choice,tuning,energy",
    list(
        itertools.product(
            ["none", "Gateway", "SyncCreation", "OCF", "custom"], [False, True], [False, True]
        )
    ),
)
def test_optional_modules_are_explicit_exact_and_never_remove_surrounding_holds(
    choice, tuning, energy
):
    from ocf_tools.complete_session import _slot_keys
    from ocf_tools.content import load_layers

    template = load_template(ROUTINE)
    supplied = {"affirmation": "Explicit custom fixture."} if choice == "custom" else {}
    enabled = (["resonant-tuning"] if tuning else []) + (["energy-ball"] if energy else [])
    doc = compose(
        template,
        supplied,
        title="Options",
        slot_keys=_slot_keys(load_layers("OCF-SEN-001")["bindings"], template),
        affirmation=choice,
        enabled_stages=enabled,
        locale="en-US",
    )
    resolved = resolve_document(doc, "en-US")
    events = {e["id"]: e for e in iter_events(resolved)}
    assert events["body-comfort.breathing-hold"]["timing"]["pause_after"] == 20
    assert events["transmutation-box.place"]["timing"]["pause_after"] == 20
    aff = [e for e in events if e.startswith("affirmation.")]
    assert aff == (
        []
        if choice == "none"
        else ["affirmation.begin", "affirmation.practice", "affirmation.complete"]
    )
    if choice != "none":
        practice = events["affirmation.practice"]
        assert practice.get("text") == (
            "Explicit custom fixture."
            if choice == "custom"
            else LocaleCatalog()
            .with_revision(REVISION, "en-US")
            .resource(
                "hplus.optional.affirmation." + choice.lower(),
                "en-US",
                domain="narration",
                fallback=False,
            )[0]
            .text
        )
    for name, enabled in (("resonant-tuning", tuning), ("energy-ball", energy)):
        ids = [i for i in events if i.startswith(name + ".")]
        assert ids == ([name + ".begin", name + ".practice", name + ".complete"] if enabled else [])
        if enabled:
            assert not events[name + ".practice"].get("text")
            assert events[name + ".practice"]["timing"]["pause_after"] == 15


def test_complete_api_selects_optional_resources_and_invalid_custom_options_fail():
    plan, doc = routine(
        overrides={"affirmation": "Gateway", "enabled_stages": ["resonant-tuning", "energy-ball"]}
    )
    assert {s["id"] for s in doc["sections"]} >= {"affirmation", "resonant-tuning", "energy-ball"}
    assert plan["resolved_overrides"]["affirmation"] == "Gateway"
    for overrides in (
        {"affirmation": "unknown"},
        {"affirmation": "custom"},
        {"affirmation": "custom", "custom_affirmation": "  "},
        {"affirmation": "Gateway", "custom_affirmation": "Conflicting."},
        {"enabled_stages": ["unknown"]},
        {
            "affirmation": "custom",
            "custom_affirmation": "Fixture.",
            "custom_affirmation_locale": "es",
        },
    ):
        with pytest.raises(OCFError):
            build_complete_session_plan("OCF-SEN-001", overrides=overrides)
    with pytest.raises(OCFError):
        LocaleCatalog().with_revision(REVISION, "es")


def test_missing_selected_preset_never_substitutes_another_preset_or_english():
    from ocf_tools import locale as locales

    source_reader = locales.load_yaml_file

    def reader(path):
        data = source_reader(path)
        if path.name == "shared-session-003.yaml":
            data = copy.deepcopy(data)
            data["entries"].pop("hplus.optional.affirmation.gateway")
        return data

    catalog = LocaleCatalog(reader=reader)
    template = load_template(LEARNING)
    doc = compose(template, {}, title="Missing preset", affirmation="Gateway", locale="en-US")
    with pytest.raises(OCFError):
        resolve_document(doc, "en-US", catalog=catalog)


def test_explicit_legacy_custom_is_literal_data_and_uses_shared_wrappers():
    template = load_template(LEARNING)
    text = "Explicit {{literal data}}, not executable syntax."
    doc = compose(
        template,
        {"affirmation": text},
        title="Literal custom",
        enabled_stages=["affirmation"],
        locale="en-US",
    )
    resolved = resolve_document(doc, "en-US")
    events = {e["id"]: e for e in iter_events(resolved)}
    assert doc["affirmation_selection"] == "custom"
    assert events["affirmation.practice"]["text"] == text
    assert events["affirmation.begin"]["narration_key"] == "hplus.optional.affirmation.begin"
    assert events["affirmation.complete"]["narration_key"] == "hplus.optional.affirmation.complete"


def test_function_optional_overrides_keep_one_compact_baseline_and_custom_data(monkeypatch):
    from ocf_tools import complete_session, session_plans
    from ocf_tools.content import load_layers

    layers = copy.deepcopy(load_layers("OCF-SEN-001"))
    layers["bindings"]["session_overrides"] = {
        "affirmation": "custom",
        "custom_affirmation": "Explicit function custom fixture.",
        "custom_affirmation_locale": "en-US",
    }
    monkeypatch.setattr(complete_session, "load_layers", lambda owner: copy.deepcopy(layers))
    monkeypatch.setattr(session_plans, "load_layers", lambda owner: copy.deepcopy(layers))
    compact, shared, expanded = session_plans.source_plan("OCF-SEN-001")
    assert compact["overrides"]["settings"]["affirmation"] == "custom"
    assert not any(r["key"].startswith("hplus.optional.affirmation.") for r in shared["resources"])
    assert any(
        e.get("text") == "Explicit function custom fixture."
        for e in iter_events(expanded["template_plan"])
    )


@pytest.mark.parametrize("owner", ["OCF-FND-002", "OCF-SEN-001"])
def test_real_default_cli_route_uses_v3_without_forcing_a_template(owner, monkeypatch, capsys):
    from ocf_tools import cli, narration_first

    monkeypatch.setattr(
        narration_first,
        "_voice_profile",
        lambda *args: (
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
    data = json.loads(capsys.readouterr().out)
    assert data["session_plan"]["template"]["id"] == ROUTINE
    doc = resolve_document(data["session_plan"]["template_plan"], "en-US")
    assert doc["narration_revision"] == REVISION
    assert not any(e["id"].startswith("focus-ten.count-") for e in iter_events(doc))


def test_learning_selector_is_a_working_cli_composition_not_an_orphan(tmp_path, capsys):
    from ocf_tools import cli

    output = tmp_path / "learning.yaml"
    assert (
        cli.main(
            [
                "session",
                "compose",
                "--template",
                LEARNING,
                "--locale",
                "en-US",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    from ocf_tools.utils import yaml_safe_load

    doc = yaml_safe_load(output.read_text(encoding="utf-8"))
    assert doc["narration_revision"] == REVISION and "function_id" not in doc
    assert (
        len([e for e in iter_events(doc) if e.get("semantic") == "focus.eleven.transition.open"])
        == 3
    )
    assert not any(e.get("narration_key") == "hplus.shared.waking.begin" for e in iter_events(doc))


def test_packaged_learning_dependencies_include_only_explicit_shared_authorities(tmp_path):
    from tools.build_package_data import stage_data

    output = tmp_path / "data"
    result = stage_data(REPO_ROOT, output)
    assert (output / "function-content/shared-state-cues.yaml").is_file()
    assert (output / "audio/templates/pacing/OCF-PACING-HPLUS-LOCKED-007.yaml").is_file()
    assert (output / "audio/templates/sessions/OCF-TPL-SESSION-PREP-LEARN-002.yaml").is_file()
    assert {p for p in result["included"] if p.startswith("function-content/")} == {
        "function-content/shared-state-cues.yaml",
        "function-content/command-procedures.yaml",
    }


def test_routine_timeline_preserves_effective_contract_and_one_close_ramp(monkeypatch):
    monkeypatch.setattr(
        "ocf_tools.audio_build._resolve_background_manifest",
        lambda ref: {"id": ref, "engine": "reference-master"},
    )
    plan, doc = routine()
    cues, total = synthetic_timeline(doc)
    program = semantic_dsp.plan_program(doc, cues, total, plan["resolved_dsp_profile"])
    assert [t["event_id"] for t in program["transitions"]] == ["open.transition", "close.close"]
    assert not any(t["event_id"] == "focus-ten.transition" for t in program["transitions"])
    report = {
        "function_id": "OCF-SEN-001",
        "narration_timing": {"cues": cues},
        "state_transitions": program["transitions"],
        "stages": plan["stages"],
        "dsp_profile": {"selections": plan["dsp_profile"]["states"]},
        "measurements": {"duration_seconds": total},
    }
    audit = audit_shared_v3(report, pacing=plan["resolved_pacing_profile"])
    assert audit["successor_checks"] == "PASS"
    assert list(audit["holds_seconds"].values()) == pytest.approx([20, 20, 40, 15, 60, 60, 60, 3])
    bad = copy.deepcopy(report)
    next(c for c in bad["narration_timing"]["cues"] if c["id"] == "close.confirmed")["at"] = (
        program["transitions"][-1]["start_s"]
    )
    with pytest.raises(OCFError):
        audit_shared_v3(bad, pacing=plan["resolved_pacing_profile"])


def test_learning_is_one_preparation_three_visits_510_seconds_and_ten_to_one(monkeypatch):
    monkeypatch.setattr(
        "ocf_tools.audio_build._resolve_background_manifest",
        lambda ref: {"id": ref, "engine": "reference-master"},
    )
    doc = lesson()
    events = {e["id"]: e for e in iter_events(doc)}
    assert "function_id" not in doc
    assert sum(e.get("narration_key") == "hplus.shared.body-comfort" for e in events.values()) == 1
    assert len([e for e in events.values() if e["id"].startswith("relaxation.")]) == 11
    assert not any(
        e.get("slot_ref") == "function_body" or e["id"].startswith(("sleep20-", "focus20-"))
        for e in events.values()
    )
    assert not any(e.get("narration_key") == "hplus.shared.focus11.ready" for e in events.values())
    waits = [events["learning-intro.speech"]["timing"]["pause_after"]]
    waits += [events[f"ten-rest-{i}.hold"]["timing"]["pause_after"] for i in range(1, 4)]
    waits += [events[f"open-{i}.ready"]["timing"]["pause_after"] for i in range(1, 4)]
    assert waits == [60] * 4 + [90] * 3 and sum(waits) == 510
    assert events["focus-ten.ready"]["timing"]["pause_after"] == 0
    assert [events[f"open-{i}.prepare"]["narration_key"] for i in range(1, 4)] == [
        "hplus.shared.focus11.open.prepare",
        "preparation.learning.v3.open-2",
        "preparation.learning.v3.open-3",
    ]
    for i in range(1, 4):
        assert events[f"close-{i}.close"]["text"].splitlines().count("Ten.") == 4
    return_pacing = plan_event_pacing(doc, events["return.begin"])
    assert [
        u["text"] for u in return_pacing["units"] if u["kind"] in {"countdown", "final_countdown"}
    ] == [n + "." for n in reversed(NUMBERS)]
    assert "Plus One Awake" not in "\n".join(e.get("text", "") for e in events.values())
    cues, total = synthetic_timeline(doc)
    profile = semantic_dsp.load_profile("OCF-DSP-PREP-LEARN-002")
    program = semantic_dsp.plan_program(doc, cues, total, profile)
    assert [t["to"] for t in program["transitions"]] == ["focus-11", "focus-10"] * 3
    assert not any(t["event_id"] == "focus-ten.transition" for t in program["transitions"])
    by_id = {c["id"]: c for c in cues}
    for i in range(1, 4):
        close = next(t for t in program["transitions"] if t["event_id"] == f"close-{i}.close")
        assert close["end_s"] - close["start_s"] == pytest.approx(10)
        assert by_id[f"close-{i}.confirmed"]["at"] >= close["end_s"]


@pytest.mark.parametrize("occurrence", [None, 0, 5, True, 1.5, 4])
def test_repeated_anchor_occurrence_is_explicit_not_number_driven(monkeypatch, occurrence):
    monkeypatch.setattr(
        "ocf_tools.audio_build._resolve_background_manifest",
        lambda ref: {"id": ref, "engine": "reference-master"},
    )
    profile = semantic_dsp.load_profile("OCF-DSP-HPLUS-LOCKED-004")
    profile.update(
        initial_state="focus-11",
        default_background_state="focus-11",
        ignored_state_events=[],
        stage_backgrounds={},
    )
    anchor = profile["transition_end_anchors"]["close.close"]
    if occurrence is None:
        anchor.pop("unit_occurrence")
    else:
        anchor["unit_occurrence"] = occurrence
    doc = {
        "timeline": [
            {
                "id": "close.close",
                "semantic": "focus.eleven.close",
                "dsp": {"state": {"from": "focus-11", "to": "focus-10"}, "transition_s": 10},
            }
        ]
    }
    units = [
        {
            "text": "Ten.",
            "start_seconds": 120 + i * 10,
            "end_seconds": 121 + i * 10,
            "audible_end_seconds": 120.9 + i * 10,
        }
        for i in range(4)
    ]
    cues = [{"id": "close.close", "at": 100, "end": 180, "duration": 80, "spoken_units": units}]
    if occurrence != 4:
        with pytest.raises(OCFError):
            semantic_dsp.plan_program(doc, cues, 200, profile)
    else:
        program = semantic_dsp.plan_program(doc, cues, 200, profile)
        assert len(program["transitions"]) == 1
        assert program["transitions"][0]["end_s"] == pytest.approx(150.9)
