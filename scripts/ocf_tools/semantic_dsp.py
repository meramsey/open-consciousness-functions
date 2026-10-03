"""Configurable semantic DSP dispatch; event identities never name a backend."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .indexes import load_yaml_file
from .locale import iter_events
from .paths import REPO_ROOT
from .utils import OCFError
from .validators import _load_schema, validate_against_schema

PROFILES_DIR = REPO_ROOT / "audio/background/state-profiles"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_profile(reference: str | Path) -> dict:
    path = Path(reference).expanduser()
    if not path.is_file():
        path = PROFILES_DIR / f"{reference}.yaml"
    if not path.is_file():
        raise OCFError(f"semantic DSP profile not found: {reference}")
    data = load_yaml_file(path)
    errors = validate_against_schema(data, _load_schema("semantic-dsp-profile.schema.json"))
    if errors:
        raise OCFError("semantic DSP profile: " + " | ".join(errors))
    return data


def plan_program(doc: dict, event_timing: list[dict], duration: float, profile: dict) -> dict:
    """Resolve required states and measured transition windows before synthesis."""
    errors = validate_against_schema(profile, _load_schema("semantic-dsp-profile.schema.json"))
    if errors:
        raise OCFError("semantic DSP profile: " + " | ".join(errors))
    if not math.isfinite(duration) or duration <= 0:
        raise OCFError("semantic DSP requires a finite positive session duration")
    events = list(iter_events(doc))
    timing = {row["id"]: row for row in event_timing}
    if len(timing) != len(event_timing):
        raise OCFError("duplicate IDs in measured semantic timing ledger")
    current = profile["initial_state"]
    required = {current}
    transitions = []
    for event in events:
        directive = (event.get("dsp") or {}).get("state")
        if directive is None:
            continue
        if event["id"] not in timing:
            raise OCFError(f"state event {event['id']} has no measured semantic timing")
        target = directive if isinstance(directive, str) else directive.get("to")
        stated_from = directive.get("from") if isinstance(directive, dict) else None
        if not target:
            raise OCFError(f"state event {event['id']} has no target state")
        if stated_from and stated_from != current:
            raise OCFError(
                f"state event {event['id']}: from {stated_from} disagrees with active {current}"
            )
        start = float(timing[event["id"]]["at"])
        candidates = [
            float(timing[child["id"]]["at"])
            for child in events
            if child.get("after") == event["id"]
            and child["id"] in timing
            and (child.get("timing") or {}).get("anchor") in ("speech-end", "event-end")
            and float(timing[child["id"]]["at"]) > start
        ]
        declared = (event.get("dsp") or {}).get("transition_s")
        if any(item["state_event"] == event["id"] for item in profile.get("approaches", [])):
            end = start
            provenance = "configured approach arrival; anchor validation follows"
        elif declared is not None:
            end = start + float(declared)
            provenance = "explicit DSP transition duration"
        elif candidates:
            end = min(candidates)
            provenance = "measured end-dependent semantic anchor"
        else:
            end = start + float(profile["transitions"]["fallback_seconds"])
            provenance = "profile design-selected fallback; no pre-event induction inference"
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= duration):
            raise OCFError(f"invalid state transition window: {event['id']}")
        if transitions and start < transitions[-1]["end_s"] - 1e-6:
            raise OCFError(
                "overlapping state transition windows; configure explicitly rather than silently retime"
            )
        transitions.append(
            {
                "event_id": event["id"],
                "semantic": event.get("semantic"),
                "from": current,
                "to": target,
                "start_s": start,
                "end_s": end,
                "envelope_provenance": provenance,
            }
        )
        required.update((current, target))
        current = target
    if not transitions:
        raise OCFError("semantic DSP requested but session contains no state directives")
    missing = required - profile["states"].keys()
    if missing:
        raise OCFError("required state DSP is not configured: " + ", ".join(sorted(missing)))
    approaches = []
    by_id = {event["id"]: event for event in events}
    for declaration in profile.get("approaches", []):
        state_event = declaration["state_event"]
        owning = next((row for row in transitions if row["event_id"] == state_event), None)
        if owning is None or owning["to"] != declaration["state"] or owning["to"] == owning["from"]:
            raise OCFError(
                "DSP approach must own a distinct arrival directive selecting its target state"
            )
        if any(row["state_event"] == state_event for row in approaches):
            raise OCFError("duplicate DSP approach for the same arrival directive")
        anchors = [declaration[key] for key in ("begin_event", "established_event", "state_event")]
        if any(anchor not in by_id or anchor not in timing for anchor in anchors):
            raise OCFError("DSP approach anchor missing from session/measured ledger")
        try:
            start, established, arrival = [float(timing[anchor]["at"]) for anchor in anchors]
        except (TypeError, ValueError, KeyError) as exc:
            raise OCFError("DSP approach anchors require measured numeric times") from exc
        if not (
            all(math.isfinite(value) for value in (start, established, arrival))
            and 0 <= start < established <= arrival <= duration
        ):
            raise OCFError("invalid DSP approach window: begin < established <= arrival required")
        if any(
            row is not owning and row["start_s"] < arrival and row["end_s"] > start
            for row in transitions
        ):
            raise OCFError("DSP approach overlaps another state transition")
        if any(start < row["arrival_s"] and arrival > row["start_s"] for row in approaches):
            raise OCFError("overlapping DSP approaches are not supported")
        if profile["states"][declaration["state"]]["mode"] != "preset":
            raise OCFError(
                "DSP approach requires an explicitly selected program, not disabled state audio"
            )
        if (by_id[state_event].get("dsp") or {}).get("transition_s") not in (None, 0):
            raise OCFError("approach arrival cannot also declare a second nonzero DSP ramp")
        approach = {
            **declaration,
            "start_s": start,
            "established_s": established,
            "arrival_s": arrival,
            "begin_semantic": by_id[declaration["begin_event"]].get("semantic"),
            "established_semantic": by_id[declaration["established_event"]].get("semantic"),
            "timing_provenance": "explicit approach event bindings resolved from measured narration ledger; state unchanged until arrival directive",
        }
        owning["approach"] = approach
        owning["end_s"] = owning["start_s"]
        owning["envelope_provenance"] = (
            "already established approach: target gain rises across the approach window, the "
            "previous state recedes across the same window, and arrival commits state without "
            "replaying a fallback ramp"
        )
        approaches.append(approach)
    selections = {}
    from .audio_build import _resolve_background_manifest

    for state in sorted(required):
        choice = profile["states"][state]
        if choice["mode"] == "disabled":
            selections[state] = {"mode": "disabled", "explicit": True}
            continue
        manifest = _resolve_background_manifest(choice["preset"])
        if not manifest:
            raise OCFError(
                f"required state {state}: unknown background manifest {choice['preset']}"
            )
        if manifest["engine"] in ("farfield", "sbagenx"):
            preset = (manifest.get("preset") or {}).get("file")
            if not preset or not (REPO_ROOT / preset).is_file():
                raise OCFError(f"required state {state}: declared preset file unavailable")
        selections[state] = {
            "mode": "preset",
            "preset_id": manifest["id"],
            "backend": manifest["engine"],
            "preset_file": (manifest.get("preset") or {}).get("file"),
            "provenance": manifest.get("provenance"),
        }
        if selections[state]["preset_file"]:
            selections[state]["preset_sha256"] = _sha(REPO_ROOT / selections[state]["preset_file"])
    program = {
        "profile_id": profile["id"],
        "profile_version": profile["version"],
        "seed": profile["seed"],
        "initial_state": profile["initial_state"],
        "curve": profile["transitions"]["curve"],
        "duration_s": duration,
        "selections": selections,
        "transitions": transitions,
    }
    if approaches:
        program["approaches"] = approaches
    return program


def gain_at(program: dict, state: str, time: float) -> float:
    gain = float(program["initial_state"] == state)
    for transition in program["transitions"]:
        if transition["to"] == transition["from"]:
            continue
        approach = transition.get("approach")
        start, end = transition["start_s"], transition["end_s"]
        if approach:
            start, end = approach["start_s"], approach["arrival_s"]
        u = (
            min(1.0, max(0.0, (time - start) / (end - start)))
            if end > start
            else float(time >= start)
        )
        if approach:
            progress = min(
                1.0,
                max(
                    0.0,
                    (time - approach["start_s"])
                    / (approach["established_s"] - approach["start_s"]),
                ),
            )
            incoming = (1 - math.cos(math.pi * progress)) / 2
        else:
            incoming = (
                (math.sin(math.pi * u / 2) if u < 1 else 1.0)
                if program["curve"] == "equal-power"
                else u
            )
        outgoing = (
            (math.cos(math.pi * u / 2) if u < 1 else 0.0)
            if program["curve"] == "equal-power"
            else 1 - u
        )
        if transition["to"] == state:
            gain += incoming
        if transition["from"] == state:
            gain -= 1 - outgoing
    return max(0.0, min(1.0, gain))


def _gain_expression(program: dict, state: str) -> str:
    pieces = [str(int(program["initial_state"] == state))]
    for transition in program["transitions"]:
        if transition["to"] == transition["from"]:
            continue
        approach = transition.get("approach")
        start, end = transition["start_s"], transition["end_s"]
        if approach:
            start, end = approach["start_s"], approach["arrival_s"]
        u = f"clip((t-{start:.9f})/{end - start:.9f},0,1)" if end > start else f"gte(t,{start:.9f})"
        if approach:
            progress = f"clip((t-{approach['start_s']:.9f})/{approach['established_s'] - approach['start_s']:.9f},0,1)"
            incoming = f"(1-cos(PI*{progress}))/2"
        else:
            incoming = (
                f"if(gte(t,{end:.9f}),1,sin(PI/2*{u}))" if program["curve"] == "equal-power" else u
            )
        outgoing = (
            f"if(gte(t,{end:.9f}),0,cos(PI/2*{u}))"
            if program["curve"] == "equal-power"
            else f"(1-{u})"
        )
        if transition["to"] == state:
            pieces.append(f"+({incoming})")
        if transition["from"] == state:
            pieces.append(f"-(1-({outgoing}))")
    return "clip(" + "".join(pieces) + ",0,1)"


def _command(command: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise OCFError(f"semantic DSP engine failed: {' '.join(command)}\n{result.stderr[-1200:]}")
    return result


def render_program(
    doc: dict,
    event_timing: list[dict],
    duration: float,
    profile: dict,
    output: Path,
    *,
    render_state: Any = None,
) -> dict:
    """Render selected independent states and continuous envelopes; never source audio fallback."""
    program = plan_program(doc, event_timing, duration, profile)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OCFError("semantic DSP requires ffmpeg; states will not silently fall back")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise OCFError("semantic DSP requires ffprobe to verify actual state duration")
    output.parent.mkdir(parents=True, exist_ok=True)
    sources = []
    commands = []
    for state, selection in program["selections"].items():
        if selection["mode"] == "disabled":
            continue
        if render_state:
            stem = Path(render_state(state, selection, program["seed"], duration))
        elif selection["backend"] == "farfield":
            from . import farfield

            stem = output.parent / f"{state}-state-seed{program['seed']}.wav"
            source = REPO_ROOT / selection["preset_file"]
            args = [
                "render",
                str(source),
                "--output",
                str(stem),
                "--seed",
                str(program["seed"]),
                "--fade",
                "0",
            ]
            try:
                result = farfield.run_farfield(args)
            except farfield.OCFFarfieldMissing as exc:
                raise OCFError(f"required state {state}: {exc}") from exc
            commands.append(["farfield", *args])
            if result.returncode or not stem.is_file():
                raise OCFError(f"required state {state}: Farfield render failed: {result.stderr}")
        else:
            from .audio_build import _render_background

            stem, note = _render_background(
                selection["preset_id"], "required", selection["backend"], max_seconds=duration
            )
            if stem is None:
                raise OCFError(f"required state {state}: {note}")
        metadata = _command(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(stem)]
        )
        import json

        if float(json.loads(metadata.stdout)["format"]["duration"]) + 0.001 < duration:
            raise OCFError(
                f"state {state} stem is shorter than the session; refusing a silent loop/fallback"
            )
        calibration = 1.0
        if profile.get("target_state_rms_dbfs") is not None:
            stats = _command(
                [ffmpeg, "-hide_banner", "-i", str(stem), "-af", "volumedetect", "-f", "null", "-"]
            )
            match = re.search(r"mean_volume: ([-0-9.]+) dB", stats.stderr)
            if not match:
                raise OCFError(f"cannot calibrate state {state} RMS")
            selection["raw_rms_dbfs"] = float(match.group(1))
            calibration = 10 ** ((profile["target_state_rms_dbfs"] - float(match.group(1))) / 20)
            selection["target_rms_dbfs"] = profile["target_state_rms_dbfs"]
        selection["renderer_gain"] = calibration
        selection["stem_sha256"] = _sha(stem)
        sources.append((state, stem, calibration))
    command = [ffmpeg, "-hide_banner", "-y"]
    chains = []
    for index, (state, stem, calibration) in enumerate(sources):
        command += ["-i", str(stem)]
        envelope = _gain_expression(program, state)
        chains.append(
            f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo,atrim=duration={duration:.9f},volume={calibration:.9f},aeval='val(0)*({envelope})|val(1)*({envelope})'[s{index}]"
        )
    if not sources:
        command += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(duration)]
    else:
        mix = "".join(f"[s{i}]" for i in range(len(sources)))
        chains.append(f"{mix}amix=inputs={len(sources)}:duration=longest:normalize=0[out]")
        command += ["-filter_complex", ";".join(chains), "-map", "[out]"]
    command += ["-ar", "44100", "-ac", "2", "-c:a", "pcm_s24le", str(output)]
    _command(command)
    commands.append(command)
    program["external_commands"] = commands
    program["output_sha256"] = _sha(output)
    program["envelope_note"] = (
        "OCF renderer crossfades across different measured generations, not a measured source morph; continuous state oscillators run on session time"
    )
    return program


def run_render_program(args: Any) -> int:
    """Render a state bed from an existing measured speech/event ledger."""
    from .transcript import load_timed_doc
    from .utils import write_text_atomic, yaml_safe_dump

    output = Path(args.output)
    if output.exists() and not args.force:
        raise OCFError(f"refusing to overwrite {output}; use --force")
    doc = load_timed_doc(args.file)
    measured = load_yaml_file(Path(args.render_manifest))
    ledger = measured.get("event_timing") or []
    duration = measured.get("total_duration_s") or measured.get("duration")
    if not ledger or duration is None:
        raise OCFError("semantic DSP needs a measured event_timing ledger and total duration")
    program = render_program(doc, ledger, float(duration), load_profile(args.dsp_profile), output)
    write_text_atomic(output.with_suffix(".render.yaml"), yaml_safe_dump(program))
    print(f"Rendered semantic DSP profile {program['profile_id']} -> {output}")
    return 0
