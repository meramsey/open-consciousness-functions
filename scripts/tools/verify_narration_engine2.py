"""Prepare private synthetic narration demos and objectively verify queued renders.

Run with .venv/bin/python. ``prepare`` never renders; its JSON includes exact
manifest paths and persistent-queue CLI argv. ``verify REPORT_DIR...`` reads
session-report.json; use --prepared DIR when reports live outside the preparation
directory. At least recorded + gain + hybrid are needed for all comparisons.
``benchmark-recording --output NEW_PRIVATE_DIR`` measures isolated cold/warm
process_recording calls, without deleting or flushing any existing cache.

SYNTHETIC SIGNAL FIXTURE: generated tones, NOT humans, speech, or audio matching
the declared transcript. Text fingerprints protect declarations only, not ASR
fidelity. All outputs remain technical candidates without listening approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
import wave
from array import array
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocf_tools import complete_session, narration_cli, recording_audio  # noqa: E402
from ocf_tools.bulk_render import verified_output  # noqa: E402
from ocf_tools.indexes import load_yaml_file  # noqa: E402
from ocf_tools.locale import iter_events, resolve_document  # noqa: E402
from ocf_tools.narration_sources import SourceResolver, text_fingerprint  # noqa: E402
from ocf_tools.paths import REPO_ROOT, work_root  # noqa: E402
from ocf_tools.semantic_dsp import load_profile, plan_program  # noqa: E402
from ocf_tools.timing import schedule_timeline  # noqa: E402
from ocf_tools.utils import OCFError, sha256_of_file  # noqa: E402

MARKER = "narration-demo.json"
LABEL = "SYNTHETIC SIGNAL FIXTURE — not human speech; does not match the spoken transcript"


def _require(condition, message):
    if not condition:
        raise OCFError(message)


def _digest(value):
    return text_fingerprint(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))


def _write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _new_private_directory(output):
    path = Path(output).expanduser().resolve()
    root = work_root().resolve()
    _require(
        path != root and path.is_relative_to(root),
        "output must be inside the OCF private workspace (.ocf-work by default)",
    )
    _require(not path.exists(), f"choose a NEW private output directory: {path}")
    path.mkdir(parents=True, mode=0o700)
    return path


def _contained(root, name):
    path = (root / name).resolve()
    _require(
        not Path(name).is_absolute() and path.is_relative_to(root),
        "artifact path escapes its directory",
    )
    return path


def write_fixture(path, duration_s, channels, *, sample_rate=44100):
    """Stream bounded PCM blocks: 100ms ramps, known independent L/R test tones.

    These oscillator frequencies identify test signals ONLY, never DSP states.
    """
    frames = round(duration_s * sample_rate)
    ramp = min(round(0.1 * sample_rate), frames // 2)
    with path.open("xb") as output, wave.open(output, "wb") as writer:
        writer.setparams((channels, 2, sample_rate, 0, "NONE", "not compressed"))
        for start in range(0, frames, 4096):
            pcm = array("h")
            for frame in range(start, min(frames, start + 4096)):
                envelope = min(1.0, frame / max(1, ramp), (frames - 1 - frame) / max(1, ramp))
                for channel in range(channels):
                    frequency = (337, 593)[channel]
                    pcm.append(
                        round(
                            4096
                            * envelope
                            * math.sin(2 * math.pi * frequency * frame / sample_rate)
                        )
                    )
            if sys.byteorder != "little":
                pcm.byteswap()
            writer.writeframesraw(pcm.tobytes())
    return {
        "file": path.name,
        "sha256": sha256_of_file(path),
        "duration_s": frames / sample_rate,
        "channels": channels,
        "sample_rate": sample_rate,
        "ramp_s": ramp / sample_rate,
    }


def fixture_durations(document, profile):
    """Use explicit state directives and dependency edges, never prose matching."""
    events = {event["id"]: event for event in iter_events(document)}
    durations = {key: 2.0 for key, event in events.items() if event.get("text", "").strip()}
    bindings = []
    ignored = set(profile.get("ignored_state_events", []))
    for event in events.values():
        dsp = event.get("dsp", {})
        if event["id"] in ignored or not dsp.get("state") or not dsp.get("transition_s"):
            continue
        span = float(dsp["transition_s"])
        # Both sides are conservative; the canonical transition event itself is
        # still scheduled by the normal timing service, including its duration.
        selected = []
        parent = events.get(event.get("after"))
        while parent and parent["id"] not in durations:
            parent = events.get(parent.get("after"))
        if parent:
            selected.append(parent["id"])
        pending = [event["id"]]
        while pending:
            previous = pending.pop()
            for child in events.values():
                if child.get("after") != previous:
                    continue
                if child["id"] in durations:
                    selected.append(child["id"])
                else:
                    pending.append(child["id"])
        for key in selected:
            durations[key] = max(durations[key], 30.0, span + 5)
        bindings.append(
            {"event_id": event["id"], "transition_s": span, "spoken_fixture_events": selected}
        )
    return durations, bindings


def _queue_argv(function_id, voice, locale, path):
    arguments = {
        "function_id": function_id,
        "manifest": str(path),
        "voice": voice,
        "locale": locale,
        "pacing": "normal",
    }
    return [
        str(REPO_ROOT / ".venv/bin/python"),
        str(REPO_ROOT / "scripts/ocf.py"),
        "dev",
        "ocf_start_narration_render",
        "--arguments",
        json.dumps(arguments),
    ]


def prepare(
    output, function_id="OCF-SLP-005", voice="OCF-VOICE-0002", locale="en-US", tts_event=None
):
    document = narration_cli.session_document(function_id, locale)
    profile = load_profile(document["semantic_dsp_profile"])
    durations, bindings = fixture_durations(document, profile)
    spoken = [event for event in iter_events(document) if event["id"] in durations]
    _require(spoken, "session has no spoken events")
    selected = tts_event or spoken[0]["id"]
    _require(selected in durations, "--tts-event must identify an actual spoken event")
    # Fail before making files if the selected voice is not the requested Piper profile.
    from ocf_tools.voice import load_voice_profiles

    voice_profile = next((item for item in load_voice_profiles() if item.get("id") == voice), None)
    _require(
        voice_profile and voice_profile.get("backend") == "piper",
        "hybrid demo requires an existing Piper voice profile",
    )
    root = _new_private_directory(output)
    assets = root / "assets"
    assets.mkdir()
    fixtures = {}
    recordings, choices = {}, {}
    for index, event in enumerate(spoken):
        key = event["id"]
        duration = durations[key]
        channels = 1 if index % 2 == 0 else 2
        identity = (duration, channels)
        if identity not in fixtures:
            name = f"SYNTHETIC-SIGNAL-FIXTURE-{duration:g}s-{channels}ch.wav"
            fixtures[identity] = write_fixture(assets / name, duration, channels)
        fixture = fixtures[identity]
        recordings[key] = {
            "file": "assets/" + fixture["file"],
            "sha256": fixture["sha256"],
            "text_sha256": text_fingerprint(event["text"]),
            "locale": locale,
            "speaker": "SYNTHETIC-SIGNAL-FIXTURE-NOT-A-HUMAN",
            "version": "synthetic-signal/1",
            "original_format": "generated PCM16 WAV; no speech",
            "approval": "pending",
            "transcription_reference": "DECLARATION ONLY: canonical text fingerprint; signal contains no matching speech",
            "rights": {
                "consent": "synthetic-fixture",
                "license": "original generated test signal",
                "redistribution_permission": False,
            },
            "target": {"event_id": key},
        }
        choices[key] = {"source": "recording", "recording_id": key}
    recorded = {
        "schema_version": "2.0",
        "id": "synthetic-signal-demo-recorded",
        "locale": locale,
        "mode": "recording",
        "fallback": "error",
        "default_voice": voice,
        "output_channels": 2,
        "recordings": recordings,
        "events": choices,
    }
    hybrid = deepcopy(recorded)
    hybrid.update(id="synthetic-signal-demo-hybrid", mode="hybrid")
    hybrid["events"][selected] = {"source": "tts", "voice": voice}
    gain_event = spoken[0]["id"]
    gain = deepcopy(recorded)
    gain["id"] = "synthetic-signal-demo-gain"
    gain["events"][gain_event]["gain_db"] = -6
    mismatch = deepcopy(recorded)
    mismatch["id"] = "synthetic-signal-demo-intentional-stale-fingerprint"
    mismatch["recordings"][gain_event]["text_sha256"] = text_fingerprint(
        "INTENTIONALLY STALE SYNTHETIC FIXTURE DECLARATION"
    )
    manifests = {}
    for variant, config in (
        ("recorded", recorded),
        ("hybrid", hybrid),
        ("gain", gain),
        ("mismatch", mismatch),
    ):
        path = root / f"{variant}.json"
        _write_json(path, config)
        if variant == "mismatch":
            _expect_mismatch(document, path)
        else:
            SourceResolver(document, path, locale=locale)
        manifests[variant] = {"path": path.name, "sha256": sha256_of_file(path)}
    ledger = schedule_timeline(document, durations)
    program = plan_program(document, ledger, max(row["end"] for row in ledger) + 1, profile)
    marker = {
        "kind": "ocf-synthetic-narration-demo",
        "version": 1,
        "label": LABEL,
        "function_id": function_id,
        "locale": locale,
        "voice": voice,
        "canonical_document_sha256": _digest(document),
        "dsp_profile_sha256": _digest(profile),
        "tts_event": selected,
        "gain_event": gain_event,
        "gain_db": -6,
        "spoken_event_count": len(spoken),
        "fixture_durations_s": durations,
        "transition_fixture_bindings": bindings,
        "planned_transitions": program["transitions"],
        "planned_duration_s": program["duration_s"],
        "fixtures": [
            {**fixture, "file": "assets/" + fixture["file"]} for fixture in fixtures.values()
        ],
        "manifests": manifests,
        "transcript_verified": False,
        "listening_approval": None,
        "content_verification": "Expected text hashes protect declarations only; no ASR fidelity or matching speech.",
    }
    _write_json(root / MARKER, marker)
    (root / "SYNTHETIC-SIGNAL-FIXTURE.txt").write_text(
        LABEL
        + "\n"
        + marker["content_verification"]
        + "\nApproval: pending; listening approval: unset.\n",
        encoding="utf-8",
    )
    return {
        **marker,
        "prepared_directory": str(root),
        "marker": str(root / MARKER),
        "manifest_paths": {key: str(root / item["path"]) for key, item in manifests.items()},
        "queue_cli_argv": {
            key: _queue_argv(function_id, voice, locale, root / manifests[key]["path"])
            for key in ("recorded", "hybrid", "gain")
        },
        "verify_cli_argv": [
            str(REPO_ROOT / ".venv/bin/python"),
            str(Path(__file__).resolve()),
            "verify",
            "--prepared",
            str(root),
            "REPORT_DIR...",
        ],
    }


def _expect_mismatch(document, path):
    try:
        SourceResolver(document, path)
    except OCFError as exc:
        _require(
            "source text fingerprint mismatch" in str(exc),
            f"mismatch failed for an unexpected reason: {exc}",
        )
        return str(exc)
    raise OCFError("intentional stale fingerprint was unexpectedly accepted")


def load_preparation(root):
    root = Path(root).expanduser().resolve()
    marker = json.loads((root / MARKER).read_text(encoding="utf-8"))
    _require(
        marker.get("kind") == "ocf-synthetic-narration-demo"
        and marker.get("version") == 1
        and marker.get("label") == LABEL,
        "missing or unrecognized synthetic demo marker",
    )
    for item in [*marker["fixtures"], *marker["manifests"].values()]:
        name = item.get("file", item.get("path"))
        _require(
            sha256_of_file(_contained(root, name)) == item["sha256"],
            f"prepared file changed: {name}",
        )
    document = narration_cli.session_document(marker["function_id"], marker["locale"])
    _require(
        _digest(document) == marker["canonical_document_sha256"],
        "canonical session changed since prepare; create a new demo",
    )
    profile = load_profile(document["semantic_dsp_profile"])
    _require(_digest(profile) == marker["dsp_profile_sha256"], "DSP profile changed since prepare")
    _expect_mismatch(document, root / marker["manifests"]["mismatch"]["path"])
    return root, marker, document, profile


def _source_checks(report, resolver, marker):
    expected = resolver.rows
    source = report["narration_source"]
    _require(
        source["manifest_sha256"] == resolver.report["manifest_sha256"],
        "wrong narration source manifest",
    )
    _require(
        source["mode"] == resolver.mode and source["output_channels"] == 2,
        "wrong source mode/channels",
    )
    rows = source["events"]
    _require(
        len(rows) == len(expected) and {row["event_id"] for row in rows} == set(expected),
        "incomplete or duplicate source event report",
    )
    for row in rows:
        wanted = expected[row["event_id"]]
        _require(
            all(row.get(key) == value for key, value in wanted.items()),
            f"source declaration changed: {row['event_id']}",
        )
    cues = report["narration_timing"]["cues"]
    spoken = {key: row for key, row in expected.items() if row["source"] != "silence"}
    _require(
        len(cues) == len(spoken) and {cue["id"] for cue in cues} == set(spoken),
        "missing/duplicate spoken cue receipts",
    )
    durations = {}
    for cue in cues:
        key = cue["id"]
        wanted = spoken[key]
        receipt = cue["narration_source"]
        _require(
            all(receipt.get(field) == value for field, value in wanted.items()),
            f"cue source/gain receipt mismatch: {key}",
        )
        durations[key] = float(cue["duration"])
        _require(
            math.isfinite(durations[key]) and durations[key] > 0, "invalid measured cue duration"
        )
        if wanted["source"] == "recording":
            preparation = receipt["preparation"]
            _require(
                preparation["input_sha256"] == wanted["recording"]["sha256"]
                and preparation["original_preserved"] is True,
                f"original source hash receipt mismatch: {key}",
            )
            _require(
                abs(durations[key] - marker["fixture_durations_s"][key]) < 0.002,
                f"fixture duration changed: {key}",
            )
            _require(
                preparation["processed"]["channels"] == 2,
                "recording preparation lost stereo output",
            )
        else:
            _require(
                key == marker["tts_event"]
                and receipt.get("backend") == "piper"
                and receipt.get("profile_id") == marker["voice"],
                "hybrid cue did not use the selected Piper voice",
            )
    return cues, durations


def verify_report(directory, preparation):
    root, marker, document, profile = preparation
    directory = Path(directory).expanduser().resolve()
    report_path = directory / "session-report.json"
    report_hash = sha256_of_file(report_path)
    _require(
        verified_output(
            {"key": "demo", "output_directory": str(directory), "manifest_sha256": report_hash},
            "demo",
        ),
        f"artifact hash/size verification failed: {directory}",
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _require(
        report["render_type"] == "complete-session-audition"
        and report["function_id"] == marker["function_id"]
        and report["requested_locale"] == marker["locale"],
        "wrong session/function/locale",
    )
    matches = [
        name
        for name, item in marker["manifests"].items()
        if item["sha256"] == report["narration_source"]["manifest_sha256"]
    ]
    _require(
        len(matches) == 1 and matches[0] != "mismatch",
        "report does not use a prepared valid demo manifest",
    )
    variant = matches[0]
    resolver = SourceResolver(document, root / marker["manifests"][variant]["path"])
    cues, durations = _source_checks(report, resolver, marker)
    # Recompute the full ordinary timeline from measured cue durations. This
    # catches shortened waits as well as moved state anchors in saved reports.
    ledger = schedule_timeline(document, durations)
    by_id = {row["id"]: row for row in ledger}
    for cue in cues:
        _require(
            abs(float(cue["at"]) - by_id[cue["id"]]["at"]) < 0.02,
            f"ordinary timing/waits changed at {cue['id']}",
        )
    dsp = report["dsp_profile"]
    program = plan_program(document, ledger, float(dsp["duration_s"]), profile)
    for field in (
        "profile_id",
        "profile_version",
        "seed",
        "initial_state",
        "default_background_state",
        "curve",
        "selections",
        "ignored_state_directives",
        "stage_backgrounds",
    ):
        _require(
            dsp.get(field) == program.get(field), f"DSP policy/preset fingerprint mismatch: {field}"
        )
    _require(
        program["ending_fade_seconds"]
        == dsp["ending_fade_seconds"]
        == report["mix"]["ending_fade_seconds"]
        == 10,
        "expected 10-second ending fade",
    )
    transitions = report["state_transitions"]
    _require(
        transitions == dsp["transitions"] and len(transitions) == len(program["transitions"]),
        "incomplete transition report",
    )
    for actual, wanted in zip(transitions, program["transitions"], strict=True):
        _require(
            all(actual[key] == wanted[key] for key in ("event_id", "from", "to")),
            "wrong semantic transition identity",
        )
        _require(
            abs(actual["start_s"] - wanted["start_s"]) < 0.02
            and abs(actual["end_s"] - wanted["end_s"]) < 0.02,
            "transition left measured canonical anchor",
        )
        _require(
            math.isclose(actual["end_s"] - actual["start_s"], 25, abs_tol=1e-6),
            "expected 25-second Focus transition",
        )
    script = resolve_document(
        load_yaml_file(_contained(directory, report["artifacts"]["session_plan"]["path"])),
        marker["locale"],
        strict=True,
    )
    # Source plans are unresolved, so compare event contracts separately from text.
    fields = ("id", "after", "at", "offset", "timing", "semantic", "dsp", "narration_key")

    def contracts(doc):
        return [{key: event[key] for key in fields if key in event} for event in iter_events(doc)]

    _require(
        contracts(script) == contracts(document),
        "saved session plan changed canonical event contracts",
    )
    stages = complete_session._build_stage_report(document, {"event_timing": ledger}, program)
    _require(len(report["stages"]) == len(stages), "incomplete stage report")
    for actual, wanted in zip(report["stages"], stages, strict=True):
        _require(
            actual["id"] == wanted["id"]
            and all(
                abs(actual[key] - wanted[key]) < 0.02 for key in ("start_seconds", "end_seconds")
            ),
            "stage timing differs from canonical full waits",
        )
    paths = {
        key: _contained(directory, report["artifacts"][key]["path"])
        for key in ("wav", "background_stem")
    }
    metrics = {}
    for key, path in paths.items():
        complete_session._verify_decode(path)
        metrics[key] = complete_session._stereo_metrics(path, sample_rate=44100)
        _require(
            metrics[key]["clipped_sample_count"] == 0
            and metrics[key]["left_peak_int16"] > 0
            and metrics[key]["right_peak_int16"] > 0,
            f"clipping or empty L/R channel: {key}",
        )
    _require(
        metrics["wav"]["frames"] == metrics["background_stem"]["frames"],
        "master/background duration mismatch",
    )
    _require(
        abs(metrics["wav"]["duration_seconds"] - program["duration_s"]) < 0.02
        and abs(program["duration_s"] - (max(row["end"] for row in ledger) + 1)) < 0.02,
        "master duration differs from full timeline plus renderer tail",
    )
    background = paths["background_stem"]
    activity = complete_session._background_activity(background, stages, program["selections"])
    analysis = complete_session._representative_audio_analysis(
        background, stages, {"event_timing": ledger}, program
    )
    continuity = complete_session._verify_background_continuity(
        background, program["duration_s"], 10
    )
    return {
        "variant": variant,
        "report_directory": str(directory),
        "report_sha256": report_hash,
        "status": "passed",
        "source_events_checked": len(resolver.rows),
        "spoken_cues_checked": len(cues),
        "gain_receipt_db": resolver.rows[marker["gain_event"]]["gain_db"],
        "preset_fingerprints": program["selections"],
        "transitions": transitions,
        "metrics": metrics,
        "background_activity": activity,
        "representative_audio_analysis": analysis,
        "background_continuity": continuity,
        "background_sha256": report["artifacts"]["background_stem"]["sha256"],
        "master_sha256": report["artifacts"]["wav"]["sha256"],
        "mix": report["mix"],
        "transcript_verified": False,
        "listening_approval": None,
    }


def compare_reports(results):
    by_variant = {row["variant"]: row for row in results}
    _require(len(by_variant) == len(results), "duplicate demo variant reports")
    comparisons = {}
    if {"recorded", "gain"} <= by_variant.keys():
        recorded, gain = by_variant["recorded"], by_variant["gain"]
        _require(
            recorded["background_sha256"] == gain["background_sha256"],
            "recorded/gain background hashes differ",
        )
        _require(
            recorded["master_sha256"] != gain["master_sha256"],
            "-6dB event gain did not change master bytes",
        )
        _require(
            math.isclose(gain["gain_receipt_db"] - recorded["gain_receipt_db"], -6, abs_tol=1e-9),
            "missing -6dB source gain receipt",
        )
        _require(
            recorded["mix"] == gain["mix"], "global mix controls changed in event-gain comparison"
        )
        comparisons["recorded_gain"] = (
            "identical background bytes; changed master bytes; -6dB event receipt"
        )
    if {"recorded", "hybrid"} <= by_variant.keys():
        _require(
            by_variant["recorded"]["preset_fingerprints"]
            == by_variant["hybrid"]["preset_fingerprints"],
            "hybrid background preset fingerprints differ",
        )
        comparisons["recorded_hybrid"] = (
            "identical background preset fingerprints; measured duration may differ"
        )
    return comparisons


def verify(directories, prepared=None):
    directories = [Path(path).expanduser().resolve() for path in directories]
    _require(directories, "provide at least one report directory")
    if prepared is None:
        candidates = [
            path for path in (directories[0], *directories[0].parents) if (path / MARKER).is_file()
        ]
        _require(candidates, "cannot locate narration-demo.json; pass --prepared PREPARED_DIR")
        prepared = candidates[0]
    preparation = load_preparation(prepared)
    results = [verify_report(path, preparation) for path in directories]
    comparisons = compare_reports(results)
    missing = sorted({"recorded", "gain", "hybrid"} - {row["variant"] for row in results})
    return {
        "status": "partial" if missing else "passed",
        "label": LABEL,
        "reports": results,
        "comparisons": comparisons,
        "missing_variants": missing,
        "mismatch_rejected": True,
        "transcript_verified": False,
        "listening_approval": None,
    }


def benchmark_recording(output, repeats=3, warm_runs=2):
    _require(
        repeats >= 2 and warm_runs >= 1,
        "benchmark requires at least two cold trials and one warm call per trial",
    )
    root = _new_private_directory(output)
    fixture = root / "SYNTHETIC-SIGNAL-FIXTURE-10s-stereo.wav"
    original = write_fixture(fixture, 10, 2)
    trials = []
    previous = os.environ.get("OCF_WORK_DIR")
    try:
        for trial in range(repeats):
            # Each cold trial gets a new workspace cache; same immutable source
            # bytes and processing identity, no global-cache deletion/flush.
            os.environ["OCF_WORK_DIR"] = str(root / f"trial-{trial + 1}")
            calls, first = [], None
            for index in range(warm_runs + 1):
                start = time.perf_counter()
                audio, receipt = recording_audio.process_recording(
                    fixture,
                    sample_rate=44100,
                    channels=2,
                    processing={"gain_db": -6},
                    expected_sha256=original["sha256"],
                )
                elapsed = time.perf_counter() - start
                _require(
                    receipt["cache_hit"] is (index > 0), "unexpected cold/warm cache-hit metadata"
                )
                if first is None:
                    first = audio
                _require(
                    audio == first
                    and hashlib.sha256(audio).hexdigest() == receipt["processed_sha256"],
                    "cold/warm cached bytes differ",
                )
                calls.append(
                    {
                        "kind": "cold" if index == 0 else "warm",
                        "wall_seconds": elapsed,
                        "cache_hit": receipt["cache_hit"],
                        "cache_key": receipt["cache_key"],
                        "processed_sha256": receipt["processed_sha256"],
                        "input": receipt["original"],
                        "output": receipt["processed"],
                    }
                )
            trials.append({"trial": trial + 1, "calls": calls})
    finally:
        if previous is None:
            os.environ.pop("OCF_WORK_DIR", None)
        else:
            os.environ["OCF_WORK_DIR"] = previous
    _require(sha256_of_file(fixture) == original["sha256"], "benchmark original changed")
    report = {
        "label": LABEL,
        "status": "passed",
        "fixture": original,
        "trials": trials,
        "median_wall_seconds": {
            kind: statistics.median(
                call["wall_seconds"]
                for trial in trials
                for call in trial["calls"]
                if call["kind"] == kind
            )
            for kind in ("cold", "warm")
        },
        "timing_scope": "process_recording wall time including verified cache reads; same 10-second source bytes, isolated cache per cold trial",
        "speed_claim": None,
        "listening_approval": None,
    }
    path = root / "benchmark-recording.json"
    _write_json(path, report)
    return {**report, "report_path": str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "prepare", help="create new private synthetic signal fixtures; no rendering"
    )
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--function", dest="function_id", default="OCF-SLP-005")
    command.add_argument("--voice", default="OCF-VOICE-0002")
    command.add_argument("--locale", default="en-US")
    command.add_argument(
        "--tts-event",
        help="explicit spoken event ID for the one Piper cue; default first spoken event",
    )
    command = commands.add_parser(
        "verify", help="verify completed reports and compare supplied variants"
    )
    command.add_argument("directories", metavar="REPORT_DIR", nargs="+", type=Path)
    command.add_argument("--prepared", type=Path, help="directory containing narration-demo.json")
    command = commands.add_parser(
        "benchmark-recording", help="optional repeated 10s recording cold/warm measurements"
    )
    command.add_argument("--output", required=True, type=Path)
    command.add_argument("--repeats", default=3, type=int)
    command.add_argument("--warm-runs", default=2, type=int)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = {"prepare": prepare, "verify": verify, "benchmark-recording": benchmark_recording}[
            command
        ](**args)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0 if result.get("status") != "partial" else 2
    except (OCFError, OSError, ValueError, KeyError, TypeError) as exc:
        print(
            json.dumps({"status": "failed", "error": str(exc), "listening_approval": None}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
