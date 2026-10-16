"""Session composition toolchain for OCF.

Implements the guided composition model from the v3 spec (Section 45.2 guided
template wizard, Section 46 reusable components under ``audio/templates/``,
Section 55 session composition templates, Section 58 function-specific
differences as slots).

A contributor supplies wording only for the declared function-specific slots.
The template supplies the original-OCF bridge: opening the channel, access
window, consolidation, the count to the twentieth state, sleep, and the count
back to waking. ``ocf session compose`` resolves a template into a canonical
timed-transcript document ready for ``ocf audio build``.

Slot files are plain text with one spoken line per line. Lines may carry an
optional ``[MM:SS.xx]`` LRC-style timestamp, which is honoured as an absolute
track time when present; untimed lines are paced evenly (``sequential``) or
spread across the whole section window (``even-span``). A section with
``repeat`` splits its window into equal bands and runs the slot lines once per
band; a section with ``from_slot`` reuses the wording of another declared slot
(e.g. the twentieth-state reinforcement repeating the focus-11 instruction).
Contributor wording is placed verbatim and never rewritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import AUDIO_SCRIPTS_DIR, REPO_ROOT, schema_path
from .transcript import format_timestamp, parse_timestamp
from .utils import OCFError, read_text, write_text_atomic, yaml_safe_dump, yaml_safe_load
from .validators import validate_against_schema

TEMPLATES_DIR = REPO_ROOT / "audio" / "templates" / "sessions"
PACING_DIR = REPO_ROOT / "audio" / "templates" / "pacing"
DEFAULT_TEMPLATE_ID = "OCF-TPL-SESSION-LEARN-001"

_LRC_LINE = re.compile(r"^\s*\[(\d{1,2}:\d{2}(?:[.,]\d{1,3})?)\]\s*(.*?)\s*$")


def load_template(
    template_ref: str, *, _parents: tuple[str, ...] = (), reader=None, lookup=None
) -> dict[str, Any]:
    """Load and validate a session template by id or by local file path.

    A bare id (e.g. ``OCF-TPL-SESSION-LEARN-001``) resolves from
    ``audio/templates/sessions/``. An existing filesystem path is loaded
    directly, allowing a citation-only, reference-derived shell to be kept
    outside the repository.
    """
    candidate = Path(template_ref).expanduser()
    if lookup is not None:
        path = lookup("template", template_ref)
    elif template_ref and (candidate.is_file() or "/" in template_ref or "\\" in template_ref):
        path = candidate
    else:
        path = TEMPLATES_DIR / f"{template_ref}.yaml"
    if reader is None and not path.is_file():
        raise OCFError(
            f"session template not found: {template_ref} "
            f"(looked in {TEMPLATES_DIR}). Use `ocf session list-templates`."
        )
    try:
        data = deepcopy(reader(path)) if reader is not None else yaml_safe_load(read_text(path))
    except Exception as exc:  # pragma: no cover - defensive
        raise OCFError(f"invalid YAML in session template {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise OCFError(f"session template {path.name} is not a mapping")
    if data.get("extends"):
        identity = str(path.resolve())
        if identity in _parents:
            raise OCFError("cyclic session template inheritance")
        from .audio_defaults import overlay

        data = overlay(
            load_template(
                data["extends"], _parents=(*_parents, identity), reader=reader, lookup=lookup
            ),
            data,
        )
    schema = _load_schema("session-template.schema.json")
    errors = validate_against_schema(data, schema)
    if errors:
        raise OCFError(f"session template {path.name} fails its schema:\n" + "\n".join(errors))
    if data.get("pacing_profile"):
        load_pacing_profile(str(data["pacing_profile"]), reader=reader, lookup=lookup)
    return data


def load_pacing_profile(
    profile_ref: str, *, _parents: tuple[str, ...] = (), reader=None, lookup=None
) -> dict[str, Any]:
    """Load one versioned session pacing policy by id or local YAML path."""
    candidate = Path(profile_ref).expanduser()
    if lookup is not None:
        path = lookup("pacing", profile_ref)
    elif profile_ref and (candidate.is_file() or "/" in profile_ref or "\\" in profile_ref):
        path = candidate
    else:
        path = PACING_DIR / f"{profile_ref}.yaml"
    if reader is None and not path.is_file():
        raise OCFError(f"session pacing profile not found: {profile_ref} (looked in {PACING_DIR})")
    try:
        data = deepcopy(reader(path)) if reader is not None else yaml_safe_load(read_text(path))
    except Exception as exc:  # pragma: no cover - defensive
        raise OCFError(f"invalid YAML in pacing profile {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise OCFError(f"session pacing profile {path.name} is not a mapping")
    if data.get("extends"):
        identity = str(path.resolve())
        if identity in _parents:
            raise OCFError("cyclic pacing profile inheritance")
        from .audio_defaults import overlay

        data = overlay(
            load_pacing_profile(
                data["extends"], _parents=(*_parents, identity), reader=reader, lookup=lookup
            ),
            data,
        )
    problems = validate_against_schema(data, _load_schema("session-pacing.schema.json"))
    if problems:
        raise OCFError(
            f"session pacing profile {path.name} fails its schema:\n" + "\n".join(problems)
        )
    narration_pacing = data.get("narration_pacing") or {}
    unknown_profiles = set(narration_pacing.get("entries", {}).values()) - set(
        narration_pacing.get("profiles", {})
    )
    if unknown_profiles:
        raise OCFError(
            "session narration pacing references unknown profile(s): "
            + ", ".join(sorted(unknown_profiles))
        )
    return data


def _pacing_value(
    profile: dict[str, Any] | None,
    key: str | None,
    *,
    allow_negative: bool = False,
) -> float | None:
    """Resolve a dotted key in a pacing profile without guessing a default."""
    if not key:
        return None
    if profile is None:
        raise OCFError(f"pacing key {key!r} requires a session pacing profile")
    value: Any = profile
    for component in key.split("."):
        if not isinstance(value, dict) or component not in value:
            raise OCFError(f"pacing profile has no value for {key!r}")
        value = value[component]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OCFError(f"pacing profile value {key!r} must be numeric")
    if not math.isfinite(float(value)) or (float(value) < 0 and not allow_negative):
        qualifier = "finite" if allow_negative else "finite and nonnegative"
        raise OCFError(f"pacing profile value {key!r} must be {qualifier}")
    return float(value)


def _slot_file_provenance(path: Path, text: str) -> dict[str, Any]:
    """Describe a slot input without copying or relocating its source text."""
    try:
        relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        relative = None
    raw = path.read_bytes()
    provenance: dict[str, Any] = {
        "file": relative,
        "filename": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    sidecar = path.with_suffix(".provenance.yaml")
    if sidecar.is_file():
        sidecar_doc = yaml_safe_load(read_text(sidecar))
        if not isinstance(sidecar_doc, dict):
            raise OCFError(f"slot provenance sidecar must be a mapping: {sidecar}")
        provenance.update(sidecar_doc)
        provenance["slot_file"] = relative
        provenance["slot_sha256"] = hashlib.sha256(raw).hexdigest()
        provenance["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return provenance


def list_templates() -> list[dict[str, Any]]:
    """Return metadata for every session template in the library."""
    if not TEMPLATES_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(TEMPLATES_DIR.glob("*.yaml")):
        try:
            data = load_template(path.stem)
        except OCFError:
            continue
        rows.append(
            {
                "id": data["id"],
                "name": data.get("name", ""),
                "origin": data.get("origin", ""),
                "description": next(iter((data.get("description") or "").splitlines()), "").strip(),
            }
        )
    return rows


def _load_schema(name: str) -> dict[str, Any]:
    with open(schema_path(name), encoding="utf-8") as handle:
        return json.load(handle)


def _parse_slot(
    text: str,
    *,
    section_start: float,
    section_end: float | None,
    line_seconds: float,
    pace: str = "sequential",
) -> list[tuple[float, str]]:
    """Resolve slot lines to (at, text) using the section's pacing mode.

    LRC timestamps are absolute track times and are honoured exactly. With
    ``sequential`` pacing, untimed lines follow in order ``line_seconds`` after
    the previous line (or after the last timestamped line); with
    ``even-span`` pacing untimed lines are spread evenly across the whole
    ``section_start``..``section_end`` window (used for the sleep-20
    reinforcement so wording floats through the entire hold).
    """
    if pace == "even-span":
        timed: list[tuple[float, str]] = []
        untimed: list[str] = []
        for raw in text.splitlines():
            match = _LRC_LINE.match(raw.strip())
            if match and parse_timestamp(match.group(1)) is not None:
                stamp = parse_timestamp(match.group(1))
                if not match.group(2).strip():
                    raise OCFError(f"unusable LRC timestamp in line: {raw!r}")
                timed.append((stamp, match.group(2).strip()))
            elif raw.strip():
                untimed.append(raw.strip())
        end = section_end if section_end is not None else section_start + line_seconds
        count = len(untimed)
        gap = (end - section_start) / (count + 1) if count else 0.0
        events = [(section_start + gap * (index + 1), line) for index, line in enumerate(untimed)]
        events.extend(timed)
        return sorted(events, key=lambda item: item[0])

    events: list[tuple[float, str]] = []
    cursor = section_start
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _LRC_LINE.match(line)
        if match:
            stamp = parse_timestamp(match.group(1))
            text_part = match.group(2).strip()
            if stamp is None or not text_part:
                raise OCFError(f"unusable LRC timestamp in line: {line!r}")
            events.append((stamp, text_part))
            cursor = stamp + line_seconds
            continue
        events.append((cursor, line))
        cursor += line_seconds
    return events


def _parse_repeated(
    text: str,
    *,
    section_start: float,
    section_end: float,
    repeat: int,
) -> list[tuple[float, str]]:
    """Resolve slot lines into repeated passes across the section window.

    The window is split into ``repeat`` equal bands and the untimed lines are
    spread evenly within each band, so the same wording drifts through the
    hold once per pass. LRC timestamps are stripped; repeated material is
    never tied to absolute times.
    """
    if repeat < 1:
        raise OCFError(f"repeat must be a positive integer, got {repeat!r}")
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _LRC_LINE.match(line)
        if match:
            if parse_timestamp(match.group(1)) is None or not match.group(2).strip():
                raise OCFError(f"unusable LRC timestamp in line: {line!r}")
            line = match.group(2).strip()
        lines.append(line)
    if not lines:
        raise OCFError("repeated section has no slot lines to schedule")
    if section_end <= section_start:
        raise OCFError("repeated section needs section_end after section_start")
    band = (section_end - section_start) / repeat
    gap = band / (len(lines) + 1)
    events: list[tuple[float, str]] = []
    for band_index in range(repeat):
        base = section_start + band * band_index
        for offset, line in enumerate(lines, start=1):
            events.append((base + gap * offset, line))
    return events


def _slot_text(section: dict[str, Any], slots: dict[str, str]) -> tuple[str | None, str]:
    """Return (slot_name, text) for a section, honouring from_slot reuse."""
    slot_name = section.get("slot")
    if slot_name and slot_name in slots:
        return slot_name, slots[slot_name]
    from_slot = section.get("from_slot")
    if from_slot:
        if from_slot not in slots:
            raise OCFError(
                f"section {section['id']} reuses slot {from_slot!r} but it was not supplied"
            )
        return None, slots[from_slot]
    return None, ""


def resolve_section_events(
    section: dict[str, Any],
    slots: dict[str, str],
    *,
    line_seconds: float,
    section_end: float | None = None,
    previous: str | None = None,
    pacing_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return the scheduled event dicts for one template section.

    Authored lines carry ``text``; keyed lines carry ``narration_key`` (plus any
    ``variables``) and are language-independent, so one template composes into
    different narration per locale.
    """
    slot_name, slot_text = _slot_text(section, slots)
    if slot_name or section.get("from_slot"):
        if section.get("pace") == "block":
            if not slot_text.strip():
                raise OCFError(f"section {section['id']} has an empty block slot")
            if section.get("repeat") is not None and section.get("repeat_pacing_key"):
                raise OCFError(
                    f"section {section['id']} cannot set both repeat and repeat_pacing_key"
                )
            repeat = section.get("repeat", 1)
            if section.get("repeat_pacing_key"):
                repeat_value = _pacing_value(pacing_profile, section["repeat_pacing_key"])
                repeat = int(repeat_value or 0)
                if repeat_value != repeat or repeat < 1:
                    raise OCFError(
                        f"section {section['id']} pacing repeat count must be a positive integer"
                    )
            repeat = int(repeat)
            if repeat < 1:
                raise OCFError(f"section {section['id']} repeat must be positive")

            if section.get("pacing_key") and "pause_before_s" in section:
                raise OCFError(
                    f"section {section['id']} cannot set both pacing_key and pause_before_s"
                )
            first_offset = section.get("pause_before_s", 0.0)
            if section.get("pacing_key"):
                first_offset = _pacing_value(pacing_profile, section["pacing_key"])
            first_offset = float(first_offset or 0.0)
            repeat_gap = 0.0
            if section.get("repeat_gap_pacing_key"):
                repeat_gap = float(
                    _pacing_value(pacing_profile, section["repeat_gap_pacing_key"]) or 0.0
                )
            pause_after = None
            if section.get("pause_after_pacing_key"):
                pause_after = _pacing_value(pacing_profile, section["pause_after_pacing_key"])

            after = section.get("after")
            if after == "$previous":
                after = previous
            if section.get("after") == "$previous" and after is None:
                raise OCFError(
                    f"section {section['id']} follows $previous but has no preceding event"
                )
            if after is None and "start" not in section:
                raise OCFError(f"block section {section['id']} needs start or after")

            events: list[dict[str, Any]] = []
            prior_id = after
            for repeat_index in range(repeat):
                event_id = (
                    f"{section['id']}.pass-{repeat_index + 1}"
                    if repeat > 1
                    else f"{section['id']}.block"
                )
                event: dict[str, Any] = {"id": event_id, "text": slot_text}
                event["slot_ref"] = slot_name or str(section.get("from_slot"))
                if section.get("semantic"):
                    event["semantic"] = section["semantic"]
                if prior_id:
                    event["after"] = prior_id
                    event["offset"] = first_offset if repeat_index == 0 else repeat_gap
                    event["timing"] = {
                        "anchor": (
                            str(section.get("after_anchor", "speech-end"))
                            if repeat_index == 0
                            else "speech-end"
                        )
                    }
                elif repeat_index == 0:
                    event["at"] = float(section["start"]) + first_offset
                if repeat_index == repeat - 1 and pause_after is not None:
                    event.setdefault("timing", {"anchor": "speech-end"})["pause_after"] = (
                        pause_after
                    )
                events.append(event)
                prior_id = event_id
            return events

        if "start" not in section:
            raise OCFError(f"line-paced slot section {section['id']} requires an absolute start")
        start = float(section["start"])
        if section.get("repeat"):
            if section_end is None:
                raise OCFError(
                    f"section {section['id']} has repeat but no section window "
                    "(missing following section start or template duration)"
                )
            return [
                {"at": at, "text": text}
                for at, text in _parse_repeated(
                    slot_text,
                    section_start=start,
                    section_end=float(section_end),
                    repeat=int(section["repeat"]),
                )
            ]
        return [
            {"at": at, "text": text}
            for at, text in _parse_slot(
                slot_text,
                section_start=start,
                section_end=section_end,
                line_seconds=line_seconds,
                pace=str(section.get("pace", "sequential")),
            )
        ]
    if "start" not in section:
        raise OCFError(f"section {section['id']} without a slot or stage requires start")
    start = float(section["start"])
    events: list[dict[str, Any]] = []
    for line in section.get("lines", []):
        event: dict[str, Any] = {
            key: value
            for key, value in line.items()
            if key not in ("at", "text", "narration_key", "variables")
        }
        if "after" in line:
            event.setdefault("offset", 0)
        else:
            event["at"] = start + float(line.get("at", 0.0))
        if line.get("narration_key"):
            event["narration_key"] = str(line["narration_key"])
            if line.get("variables"):
                event["variables"] = dict(line["variables"])
        elif "text" in line:
            event["text"] = str(line["text"])
        events.append(event)
    return events


def _apply_pacing_keys(events: list[dict[str, Any]], pacing_profile: dict[str, Any] | None) -> None:
    """Resolve authored pacing keys into numeric event timing/DSP fields."""
    for event in events:
        key = event.pop("pacing_key", None)
        if not key:
            continue
        value = _pacing_value(pacing_profile, str(key))
        if value is None:
            raise OCFError(f"pacing key {key!r} did not resolve")
        if event.get("dsp"):
            event["dsp"]["transition_s"] = value
        else:
            event.setdefault("timing", {})["pause_after"] = value


def resolve_section(
    section: dict[str, Any],
    slots: dict[str, str],
    *,
    line_seconds: float,
    section_end: float | None = None,
) -> list[tuple[float, str]]:
    """Return the scheduled (at, text) events for one template section."""
    return [
        (float(event["at"]), str(event.get("text", "")))
        for event in resolve_section_events(
            section, slots, line_seconds=line_seconds, section_end=section_end
        )
    ]


def compose(
    template: dict[str, Any],
    slots: dict[str, str],
    *,
    title: str,
    document_id: str | None = None,
    line_seconds: float | None = None,
    duration: float | None = None,
    enabled_stages: list[str] | None = None,
    function_id: str | None = None,
    pacing_profile: dict[str, Any] | str | None = None,
    slot_provenance: dict[str, Any] | None = None,
    slot_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve a session template into a canonical timed-transcript document.

    ``slots`` maps slot names to plain text; ``slot_keys`` supplies localized
    whole-block narration by key. Only slots declared by the
    template are accepted. Every declared required slot must be present;
    optional slots keep the template placeholder wording when omitted. The
    returned document records ``template`` provenance and the exact slot
    wording used (``slots``), so artifacts can be traced back to the source
    without rewriting it.
    """
    slot_keys = dict(slot_keys or {})
    if set(slot_keys) & set(slots):
        raise OCFError("a slot cannot supply both plain text and a narration key")
    slots = {**slots, **slot_keys}
    for section in template["sections"]:
        slot = section.get("slot") or section.get("from_slot")
        if slot in slot_keys and section.get("pace") != "block":
            raise OCFError("keyed slots require whole-block pacing")
    if isinstance(pacing_profile, str):
        pacing_profile = load_pacing_profile(pacing_profile)
    if pacing_profile is None and template.get("pacing_profile"):
        pacing_profile = load_pacing_profile(str(template["pacing_profile"]))

    declared: list[str] = list(template.get("slots", {}).get("required", []))
    declared += list(template.get("slots", {}).get("optional", []))
    unknown = set(slots) - set(declared)
    if unknown:
        raise OCFError(
            f"unknown slot(s) for template {template['id']}: {', '.join(sorted(unknown))}"
        )
    defaults = template.get("defaults") or {}
    missing = [s for s in template.get("slots", {}).get("required", []) if s not in slots]
    if missing:
        raise OCFError(
            f"missing required slot(s) for template {template['id']}: "
            f"{', '.join(missing)} "
            "(use --slot NAME=PATH or the matching --NAME FILE flag)"
        )

    line_seconds = (
        float(defaults.get("line_seconds", 3.0)) if line_seconds is None else line_seconds
    )
    duration = float(defaults.get("duration", 1800.0)) if duration is None else duration
    if not math.isfinite(line_seconds) or line_seconds <= 0:
        raise OCFError("line_seconds must be positive and finite")
    if not math.isfinite(duration) or duration < 0:
        raise OCFError("duration must be nonnegative and finite")
    if function_id and template.get("function_id") and function_id != template["function_id"]:
        raise OCFError("function_id conflicts with the template's command owner")

    sections_out: list[dict[str, Any]] = []
    used_slots: dict[str, list[str]] = {}
    counter = 0
    features = set(template.get("features") or []) | set(enabled_stages or [])
    available = {
        section["enabled_by"] for section in template["sections"] if section.get("enabled_by")
    }
    if features - available:
        raise OCFError(
            f"unknown optional stage feature(s): {', '.join(sorted(features - available))}"
        )
    sections = [
        section
        for section in template["sections"]
        if not section.get("enabled_by") or section["enabled_by"] in features
    ]
    starts = [float(section.get("start", 0.0)) for section in sections]
    stage_provenance = []
    previous = None

    for index, section in enumerate(sections):
        slot_name = section.get("slot")
        section_end = starts[index + 1] if index + 1 < len(starts) else float(duration)
        if section.get("stage"):
            from .semantics import load_stage, stage_events

            stage = load_stage(section["stage"])
            stage = deepcopy(stage)
            overrides = section.get("narration") or {}
            unknown_events = set(overrides) - {event["id"] for event in stage["events"]}
            if unknown_events:
                raise OCFError(
                    f"stage {section['id']}: unknown narration override event(s): {', '.join(sorted(unknown_events))}"
                )
            for event in stage["events"]:
                if event["id"] in overrides:
                    if set(overrides[event["id"]]) - {
                        "text",
                        "narration_key",
                        "slot",
                        "variables",
                        "locale",
                    }:
                        raise OCFError(
                            "narration override cannot alter semantic, DSP, cue or timing fields"
                        )
                    override = overrides[event["id"]]
                    content_fields = [
                        field for field in ("text", "narration_key", "slot") if field in override
                    ]
                    if len(content_fields) != 1:
                        raise OCFError(
                            "narration override needs exactly one text, narration_key, or slot"
                        )
                    if "slot" in override:
                        slot = str(override["slot"])
                        if slot not in slots:
                            # An optional slot may override a stage's shared
                            # default narration. If no default exists, enabling
                            # the stage without its custom resource is an error.
                            if not event.get("narration_key") and not event.get("text"):
                                raise OCFError(
                                    f"stage section {section['id']} requires supplied slot {slot!r}"
                                )
                            continue
                        event.pop("text", None)
                        event.pop("narration_key", None)
                        if slot in slot_keys:
                            event["narration_key"] = slot_keys[slot]
                        else:
                            event["text"] = slots[slot]
                        used_slots.setdefault(slot, [slots[slot]])
                        event.update(
                            {key: value for key, value in override.items() if key != "slot"}
                        )
                    else:
                        event.pop("text", None)
                        event.pop("narration_key", None)
                        event.update(override)
            events = stage_events(
                stage,
                section["id"],
                start=float(section.get("start", 0)),
                after=section.get("after"),
                previous=previous,
            )
            pacing_overrides = section.get("pacing_overrides") or {}
            if pacing_overrides:
                event_by_local_id = {
                    event["id"][len(section["id"]) + 1 :]: event
                    for event in events
                    if event["id"].startswith(section["id"] + ".")
                }
                unknown_pacing = set(pacing_overrides) - set(event_by_local_id)
                if unknown_pacing:
                    raise OCFError(
                        f"stage section {section['id']}: unknown pacing event(s): "
                        + ", ".join(sorted(unknown_pacing))
                    )
                for local_id, key in pacing_overrides.items():
                    if event_by_local_id[local_id].get("pacing_key"):
                        raise OCFError(
                            f"stage section {section['id']} sets pacing twice for {local_id}"
                        )
                    event_by_local_id[local_id]["pacing_key"] = key
            _apply_pacing_keys(events, pacing_profile)
            stage_provenance.append(
                {"id": stage["id"], "version": stage["version"], "instance": section["id"]}
            )
        else:
            stage = None
            events = resolve_section_events(
                section,
                slots,
                line_seconds=line_seconds,
                section_end=section_end,
                previous=previous,
                pacing_profile=pacing_profile,
            )
            _apply_pacing_keys(events, pacing_profile)
        timeline: list[dict[str, Any]] = []
        for event in events:
            at_seconds = float(event["at"]) if "at" in event else None
            if at_seconds is not None and at_seconds > duration:
                print(
                    f"Warning: {section['id']} event at {format_timestamp(at_seconds)} "
                    f"exceeds template duration {duration}s"
                )
            counter += 1
            timeline.append(
                {
                    "id": event.get("id", f"e{counter:03d}"),
                    **({"at": format_timestamp(at_seconds)} if at_seconds is not None else {}),
                    **{
                        key: value
                        for key, value in event.items()
                        if key
                        in (
                            "text",
                            "narration_key",
                            "variables",
                            "after",
                            "offset",
                            "semantic",
                            "dsp",
                            "auditory_cue",
                            "timing",
                            "slot_ref",
                            "state",
                            "cue_id",
                            "narration_required",
                            "intentional_repeat",
                        )
                        or key in ("function_id", "locale")
                    },
                }
            )
            previous = timeline[-1]["id"]
        if slot_name and slot_name in slots:
            if section.get("pace") == "block":
                used_slots.setdefault(slot_name, [slots[slot_name]])
            else:
                used_slots[slot_name] = [str(event.get("text", "")) for event in events]
        section_doc: dict[str, Any] = {
            "id": section["id"],
            "type": section.get("type") or (stage or {}).get("type", "custom"),
        }
        if section.get("role"):
            section_doc["role"] = section["role"]
        if section.get("gain_db") is not None and section.get("gain_db_pacing_key"):
            raise OCFError(
                f"section {section['id']} cannot set both gain_db and gain_db_pacing_key"
            )
        if section.get("gain_db_pacing_key"):
            gain = _pacing_value(pacing_profile, section["gain_db_pacing_key"], allow_negative=True)
            section_doc["gain_db"] = float(gain)
        elif section.get("gain_db") is not None:
            section_doc["gain_db"] = float(section["gain_db"])
        section_doc["timeline"] = timeline
        sections_out.append(section_doc)

    doc: dict[str, Any] = {
        "schema_version": "1.0",
        "title": title,
        "sections": sections_out,
        "template": {
            "id": template["id"],
            "version": template.get("version") or template.get("schema_version"),
            "origin": template.get("origin", "original-ocf"),
        },
        "slots": {name: text for name, text in used_slots.items() if name not in slot_keys},
    }
    if stage_provenance:
        doc["stages"] = stage_provenance
    if template.get("session_completeness"):
        doc["session_completeness"] = template["session_completeness"]
    if template.get("dsp_profile"):
        doc["semantic_dsp_profile"] = template["dsp_profile"]
    if pacing_profile:
        doc["pacing_profile"] = {
            "id": pacing_profile["id"],
            "version": pacing_profile["version"],
            "status": pacing_profile["status"],
        }
        if pacing_profile.get("narration_pacing"):
            doc["narration_pacing"] = deepcopy(pacing_profile["narration_pacing"])
        doc["template"]["pacing_profile"] = {
            "id": pacing_profile["id"],
            "version": pacing_profile["version"],
        }
    if slot_provenance:
        unknown_provenance = set(slot_provenance) - set(declared)
        if unknown_provenance:
            raise OCFError(
                "slot provenance names undeclared slot(s): " + ", ".join(sorted(unknown_provenance))
            )
        used_provenance = {
            slot: value for slot, value in slot_provenance.items() if slot in used_slots
        }
        if used_provenance:
            doc["slot_provenance"] = deepcopy(used_provenance)
    for key in ("function_id", "cue_profile", "voice_profile"):
        if template.get(key):
            doc[key] = template[key]
    if function_id:
        doc["function_id"] = function_id
    if template.get("locale"):
        doc["locale"] = str(template["locale"])
    template_source = template.get("source")
    if isinstance(template_source, dict):
        doc["source"] = dict(template_source)
    if document_id:
        doc["id"] = document_id

    if slot_keys:
        from .locale import iter_events

        for event in iter_events(doc):
            slot = event.get("slot_ref")
            if slot in slot_keys:
                event.pop("text", None)
                event["narration_key"] = slot_keys[slot]

    if doc.get("function_id"):
        from .indexes import load_all_functions
        from .locale import LocaleCatalog, iter_events

        owner = next(
            (record for record in load_all_functions() if record.id == doc["function_id"]), None
        )
        if owner is None:
            raise OCFError(f"unknown function_id: {doc['function_id']}")
        catalog = LocaleCatalog()
        for event in iter_events(doc):
            entry = catalog.canonical.get(event.get("narration_key")) if catalog.canonical else None
            if entry:
                metadata = {
                    "command": owner.canonical_command,
                    "function_name": owner.canonical_name,
                }
                values = event.setdefault("variables", {})
                for name in entry.variables:
                    if name in metadata:
                        values.setdefault(name, metadata[name])

    schema = _load_schema("timed-transcript.schema.json")
    errors = validate_against_schema(doc, schema)
    if errors:
        raise OCFError("composed document fails timed-transcript schema:\n" + "\n".join(errors))
    return doc


def run_compose(args: Any) -> int:
    """CLI handler for `ocf session compose`."""
    from .paths import ensure_dir

    template = load_template(args.template)
    slots: dict[str, str] = {}
    slot_provenance: dict[str, Any] = {}
    for flag, name in (
        (getattr(args, "opener", None), "opener"),
        (getattr(args, "focus11", None), "focus11"),
        (getattr(args, "sleep20", None), "sleep20"),
        (getattr(args, "closer", None), "closer"),
    ):
        if flag:
            path = Path(flag)
            slots[name] = read_text(path)
            slot_provenance[name] = _slot_file_provenance(path, slots[name])
    for spec in args.slot or []:
        if "=" not in spec:
            raise OCFError(f"--slot expects NAME=PATH, got {spec!r}")
        name, path_text = spec.split("=", 1)
        slot_name = name.strip()
        slot_path = Path(path_text)
        slots[slot_name] = read_text(slot_path)
        slot_provenance[slot_name] = _slot_file_provenance(slot_path, slots[slot_name])

    title = args.title or template.get("name", "OCF session")
    slot_keys = {}
    owner = getattr(args, "function", None)
    if owner and template.get("composition_kind") == "human-plus-function":
        from .locale import LocaleCatalog

        catalog = LocaleCatalog()
        for name in ("opener", "function_body", "closer"):
            if name not in slots:
                key = f"hplus.function.{owner.lower()}.{name.replace('_', '-')}"
                if not catalog.canonical or catalog.canonical.get(key) is None:
                    raise OCFError(f"function narration is not authored: {key}")
                slot_keys[name] = key
    pacing_ref = getattr(args, "pacing_profile", None) or template.get("pacing_profile")
    pacing_profile = load_pacing_profile(str(pacing_ref)) if pacing_ref else None
    doc = compose(
        template,
        slots,
        title=title,
        document_id=args.id,
        line_seconds=getattr(args, "line_seconds", None),
        duration=getattr(args, "duration", None),
        enabled_stages=getattr(args, "enable_stage", None),
        function_id=getattr(args, "function", None),
        pacing_profile=pacing_profile,
        slot_provenance=slot_provenance,
        slot_keys=slot_keys,
    )

    locale = getattr(args, "locale", None)
    if locale:
        from .locale import resolve_document

        doc = resolve_document(
            doc,
            locale,
            strict=not getattr(args, "allow_fallback", False),
        )

    if args.output:
        output = Path(args.output)
    else:
        slug = args.id or "session"
        output = AUDIO_SCRIPTS_DIR / f"{slug}.yaml"
    ensure_dir(output.parent)
    if output.exists() and not args.force:
        raise OCFError(f"Refusing to overwrite existing file: {output} (use --force)")
    body = yaml_safe_dump(doc)
    write_text_atomic(output, body)
    print(f"Composed {template['id']} -> {output} ({len(doc['sections'])} sections)")
    if template.get("content_status") == "architecture-draft":
        print(
            "Architecture draft: original narration/timing is pending; missing required narration blocks rendering."
        )
    if locale:
        print(f"Locale: {doc.get('locale')}")
    if slots:
        print(f"Slots used: {', '.join(sorted(slots))}")
    return 0


def run_list_templates() -> int:
    """CLI handler for `ocf session list-templates`."""
    rows = list_templates()
    if not rows:
        print("No session templates found.")
        return 0
    for row in rows:
        print(f"{row['id']}  [{row['origin']}]  {row['name']}")
        if row["description"]:
            print(f"    {row['description']}")
    return 0
