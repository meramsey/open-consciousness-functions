"""Configurable semantic DSP dispatch; event identities never name a backend."""

from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .indexes import load_yaml_file
from .locale import iter_events
from .paths import REPO_ROOT, cleanup_workspace_temp, workspace_run, workspace_temp_directory
from .utils import OCFError, yaml_safe_dump
from .validators import _load_schema, validate_against_schema

PROFILES_DIR = REPO_ROOT / "audio/background/state-profiles"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _duration_seconds(value: Any) -> float | None:
    """Parse the numeric/M:SS duration subset used by committed Farfield presets."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    pieces = value.strip().split(":")
    try:
        if len(pieces) == 1:
            return float(pieces[0])
        if len(pieces) == 2:
            return float(pieces[0]) * 60.0 + float(pieces[1])
        if len(pieces) == 3:
            return float(pieces[0]) * 3600.0 + float(pieces[1]) * 60.0 + float(pieces[2])
    except ValueError:
        return None
    return None


def _farfield_source_for_duration(
    source: Path, duration: float, staging_dir: Path
) -> tuple[Path, dict[str, Any] | None, Path | None]:
    """Extend only a single steady Farfield layer when a session exceeds its preset length.

    Frequencies, noise, levels, and channel parameters are copied unchanged. A
    preset with multiple fixed segments is never re-timed; the renderer will
    report that as a genuine session-duration blocker.
    """
    preset = load_yaml_file(source)
    segments = preset.get("segments") or []
    if len(segments) != 1:
        return source, None, None
    segment = segments[0]
    configured = segment.get("duration")
    if configured == "hold":
        return source, None, None
    fixed_duration = _duration_seconds(configured)
    if fixed_duration is None or duration <= fixed_duration + 0.001:
        return source, None, None
    emerge = preset.get("emerge")
    if emerge not in (None, False):
        emerge_duration = _duration_seconds((emerge or {}).get("duration_s"))
        if emerge_duration not in (None, 0.0):
            return source, None, None

    derived = dict(preset)
    derived["segments"] = [dict(segment, duration="hold")]
    derived["default_total"] = float(duration)
    descriptor, filename = tempfile.mkstemp(
        prefix=".ocf-farfield-session-duration-", suffix=".yaml", dir=staging_dir
    )
    os.close(descriptor)
    variant = Path(filename)
    variant.write_text(yaml_safe_dump(derived), encoding="utf-8", newline="\n")
    adjustment = {
        "preset_source": source.relative_to(REPO_ROOT).as_posix(),
        "configured_single_segment_duration_seconds": fixed_duration,
        "session_duration_seconds": round(duration, 3),
        "extended_seconds": round(duration - fixed_duration, 3),
        "method": "continued the existing single steady segment; preset audio parameters unchanged",
        "temporary_variant_sha256": _sha(variant),
    }
    return variant, adjustment, variant


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
    default_background = profile.get("default_background_state", profile["initial_state"])
    if default_background != profile["initial_state"]:
        raise OCFError("semantic DSP default background must be active at the initial state")
    if profile["initial_state"] not in profile["states"]:
        raise OCFError("required state DSP: initial state has no configured background selection")
    fade_seconds = float(profile.get("ending_fade_seconds", 0))
    if not math.isfinite(fade_seconds) or fade_seconds < 0:
        raise OCFError("semantic DSP ending fade must be finite and nonnegative")
    events = list(iter_events(doc))
    timing = {row["id"]: row for row in event_timing}
    if len(timing) != len(event_timing):
        raise OCFError("duplicate IDs in measured semantic timing ledger")
    current = profile["initial_state"]
    required = {current}
    transitions = []
    ignored_state_events = set(profile.get("ignored_state_events", []))
    ignored_directives = []
    observed_directives = set()
    for event in events:
        directive = (event.get("dsp") or {}).get("state")
        if directive is None:
            continue
        observed_directives.add(event["id"])
        if event["id"] in ignored_state_events:
            ignored_directives.append(
                {
                    "event_id": event["id"],
                    "semantic": event.get("semantic"),
                    "directive": directive,
                    "reason": "explicitly ignored by selected DSP profile; logical narration state is retained",
                }
            )
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
    if not transitions and not profile.get("allow_static", False):
        raise OCFError("semantic DSP requested but session contains no state directives")
    if not transitions and profile["states"][current].get("mode") != "preset":
        raise OCFError("explicit static DSP requires an audible initial-state preset")
    unknown_ignored = ignored_state_events - observed_directives
    if unknown_ignored:
        raise OCFError(
            "DSP profile ignores state event(s) absent from this session: "
            + ", ".join(sorted(unknown_ignored))
        )
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
        "default_background_state": profile.get(
            "default_background_state", profile["initial_state"]
        ),
        "curve": profile["transitions"]["curve"],
        "duration_s": duration,
        "ending_fade_seconds": min(fade_seconds, duration),
        "selections": selections,
        "transitions": transitions,
        "ignored_state_directives": ignored_directives,
        "stage_backgrounds": profile.get("stage_backgrounds", {}),
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
    fade_seconds = float(program.get("ending_fade_seconds", 0))
    if fade_seconds > 0:
        progress = min(
            1.0, max(0.0, (time - (program["duration_s"] - fade_seconds)) / fade_seconds)
        )
        gain = 0.0 if progress >= 1 else gain * math.cos(math.pi * progress / 2)
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
    envelope = "clip(" + "".join(pieces) + ",0,1)"
    fade_seconds = float(program.get("ending_fade_seconds", 0))
    if fade_seconds > 0:
        fade_start = float(program["duration_s"]) - fade_seconds
        envelope += (
            f"*if(gte(t,{program['duration_s']:.9f}),0,"
            f"cos(PI/2*clip((t-{fade_start:.9f})/{fade_seconds:.9f},0,1)))"
        )
    return envelope


def _command(command: list[str]) -> subprocess.CompletedProcess:
    result = workspace_run(command, capture_output=True, text=True, timeout=600)
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
    scratch_dir: Path | None = None,
) -> dict:
    """Render selected independent states and continuous envelopes; never source audio fallback."""
    program = plan_program(doc, event_timing, duration, profile)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OCFError("semantic DSP requires ffmpeg; states will not silently fall back")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise OCFError("semantic DSP requires ffprobe to verify actual state duration")
    own_scratch = scratch_dir is None
    scratch_dir = scratch_dir or workspace_temp_directory(prefix="ocf-dsp-render-")
    output.parent.mkdir(parents=True, exist_ok=True)
    sources = []
    commands = []
    duration_extensions = []
    for state, selection in program["selections"].items():
        cache_key, cached_stem = None, None
        if selection["mode"] == "disabled":
            continue
        if render_state:
            stem = Path(render_state(state, selection, program["seed"], duration))
        elif selection["backend"] == "farfield":
            from . import farfield

            stem = scratch_dir / f"{state}-state-seed{program['seed']}.wav"
            configured_source = REPO_ROOT / selection["preset_file"]
            from . import dsp_cache

            cache_key = dsp_cache.cache_key(configured_source, program["seed"], duration)
            cached_stem = dsp_cache.lookup(cache_key)
            source, duration_adjustment, temporary_source = _farfield_source_for_duration(
                configured_source, duration, scratch_dir
            )
            args = [
                "render",
                str(source),
                "--output",
                str(stem),
                "--duration",
                f"{duration:.3f}",
                "--seed",
                str(program["seed"]),
                "--fade",
                "0",
            ]
            try:
                if cached_stem is None:
                    result = farfield.run_farfield(args)
                else:
                    shutil.copyfile(cached_stem, stem)
                    result = subprocess.CompletedProcess([], 0, "", "")
            except farfield.OCFFarfieldMissing as exc:
                raise OCFError(f"required state {state}: {exc}") from exc
            finally:
                if temporary_source is not None:
                    temporary_source.unlink(missing_ok=True)
            if cached_stem is None:
                commands.append(["farfield", *args])
            selection["stem_cache"] = "hit" if cached_stem else "miss" if cache_key else "bypassed"
            if result.returncode or not stem.is_file():
                raise OCFError(f"required state {state}: Farfield render failed: {result.stderr}")
            if duration_adjustment:
                selection["duration_extension"] = duration_adjustment
                duration_extensions.append({"state": state, **duration_adjustment})
        else:
            from .audio_build import _render_background

            stem, note = _render_background(
                selection["preset_id"],
                "required",
                selection["backend"],
                max_seconds=duration,
                scratch_dir=scratch_dir,
            )
            if stem is None:
                raise OCFError(f"required state {state}: {note}")
        metadata = _command(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(stem)]
        )
        import json

        state_duration = float(json.loads(metadata.stdout)["format"]["duration"])
        if state_duration + 0.001 < duration:
            raise OCFError(
                f"state {state} stem ({state_duration:.3f}s) is shorter than the session "
                f"({duration:.3f}s); refusing a silent loop/fallback"
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
        if cache_key and cached_stem is None:
            from . import dsp_cache

            selection["stem_cache_stored"] = dsp_cache.store(cache_key, stem)
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
    if duration_extensions:
        program["duration_extensions"] = duration_extensions
    program["envelope_note"] = (
        "OCF renderer crossfades across different measured generations, not a measured source morph; continuous state oscillators run on session time; the configured ending fade is applied to the active bed"
    )
    if own_scratch:
        cleanup_workspace_temp(scratch_dir)
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
