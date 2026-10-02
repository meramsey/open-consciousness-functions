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

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import AUDIO_SCRIPTS_DIR, REPO_ROOT, schema_path
from .transcript import format_timestamp, parse_timestamp
from .utils import OCFError, read_text, write_text_atomic, yaml_safe_dump, yaml_safe_load
from .validators import validate_against_schema

TEMPLATES_DIR = REPO_ROOT / "audio" / "templates" / "sessions"
DEFAULT_TEMPLATE_ID = "OCF-TPL-SESSION-LEARN-001"

_LRC_LINE = re.compile(r"^\s*\[(\d{1,2}:\d{2}(?:[.,]\d{1,3})?)\]\s*(.*?)\s*$")


def load_template(template_ref: str) -> dict[str, Any]:
    """Load and validate a session template by id or by local file path.

    A bare id (e.g. ``OCF-TPL-SESSION-LEARN-001``) resolves from
    ``audio/templates/sessions/``. An existing filesystem path is loaded
    directly, allowing a citation-only, reference-derived shell to be kept
    outside the repository.
    """
    candidate = Path(template_ref).expanduser()
    if template_ref and (candidate.is_file() or "/" in template_ref or "\\" in template_ref):
        path = candidate
    else:
        path = TEMPLATES_DIR / f"{template_ref}.yaml"
    if not path.is_file():
        raise OCFError(
            f"session template not found: {template_ref} "
            f"(looked in {TEMPLATES_DIR}). Use `ocf session list-templates`."
        )
    try:
        data = yaml_safe_load(read_text(path))
    except Exception as exc:  # pragma: no cover - defensive
        raise OCFError(f"invalid YAML in session template {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise OCFError(f"session template {path.name} is not a mapping")
    schema = _load_schema("session-template.schema.json")
    errors = validate_against_schema(data, schema)
    if errors:
        raise OCFError(f"session template {path.name} fails its schema:\n" + "\n".join(errors))
    return data


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
                "description": (data.get("description") or "").splitlines()[0].strip(),
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
    lines = [line.strip() for line in text.splitlines() if line.strip()]
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
) -> list[dict[str, Any]]:
    """Return the scheduled event dicts for one template section.

    Authored lines carry ``text``; keyed lines carry ``narration_key`` (plus any
    ``variables``) and are language-independent, so one template composes into
    different narration per locale.
    """
    slot_name, slot_text = _slot_text(section, slots)
    start = float(section["start"])
    if slot_name or section.get("from_slot"):
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
) -> dict[str, Any]:
    """Resolve a session template into a canonical timed-transcript document.

    ``slots`` maps slot names to plain text. Only slots declared by the
    template are accepted. Every declared required slot must be present;
    optional slots keep the template placeholder wording when omitted. The
    returned document records ``template`` provenance and the exact slot
    wording used (``slots``), so artifacts can be traced back to the source
    without rewriting it.
    """
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

    line_seconds = line_seconds or float(defaults.get("line_seconds", 3.0))
    duration = duration or float(defaults.get("duration", 1800.0))

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
                        "variables",
                        "locale",
                    }:
                        raise OCFError(
                            "narration override cannot alter semantic, DSP, cue or timing fields"
                        )
                    if ("text" in overrides[event["id"]]) == (
                        "narration_key" in overrides[event["id"]]
                    ):
                        raise OCFError("narration override needs exactly one text or narration_key")
                    event.pop("text", None)
                    event.pop("narration_key", None)
                    event.update(overrides[event["id"]])
            events = stage_events(
                stage,
                section["id"],
                start=float(section.get("start", 0)),
                after=section.get("after"),
                previous=previous,
            )
            stage_provenance.append(
                {"id": stage["id"], "version": stage["version"], "instance": section["id"]}
            )
        else:
            stage = None
            events = resolve_section_events(
                section, slots, line_seconds=line_seconds, section_end=section_end
            )
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
            used_slots[slot_name] = [str(event.get("text", "")) for event in events]
        section_doc: dict[str, Any] = {
            "id": section["id"],
            "type": section.get("type") or (stage or {}).get("type", "custom"),
        }
        if section.get("role"):
            section_doc["role"] = section["role"]
        if section.get("gain_db") is not None:
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
        "slots": used_slots,
    }
    if stage_provenance:
        doc["stages"] = stage_provenance
    for key in ("function_id", "cue_profile"):
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
    for flag, name in (
        (getattr(args, "opener", None), "opener"),
        (getattr(args, "focus11", None), "focus11"),
        (getattr(args, "sleep20", None), "sleep20"),
        (getattr(args, "closer", None), "closer"),
    ):
        if flag:
            slots[name] = read_text(Path(flag))
    for spec in args.slot or []:
        if "=" not in spec:
            raise OCFError(f"--slot expects NAME=PATH, got {spec!r}")
        name, path_text = spec.split("=", 1)
        slots[name.strip()] = read_text(Path(path_text))

    title = args.title or template.get("name", "OCF session")
    doc = compose(
        template,
        slots,
        title=title,
        document_id=args.id,
        line_seconds=getattr(args, "line_seconds", None),
        duration=getattr(args, "duration", None),
        enabled_stages=getattr(args, "enable_stage", None),
        function_id=getattr(args, "function", None),
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
