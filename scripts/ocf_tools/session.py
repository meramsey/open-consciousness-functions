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
        events = [
            (section_start + gap * (index + 1), line)
            for index, line in enumerate(untimed)
        ]
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
                f"section {section['id']} reuses slot {from_slot!r} "
                f"but it was not supplied"
            )
        return None, slots[from_slot]
    return None, ""


def resolve_section(
    section: dict[str, Any],
    slots: dict[str, str],
    *,
    line_seconds: float,
    section_end: float | None = None,
) -> list[tuple[float, str]]:
    """Return the scheduled (at, text) events for one template section."""
    slot_name, slot_text = _slot_text(section, slots)
    start = float(section["start"])
    if slot_name or section.get("from_slot"):
        if section.get("repeat"):
            if section_end is None:
                raise OCFError(
                    f"section {section['id']} has repeat but no section window "
                    "(missing following section start or template duration)"
                )
            return _parse_repeated(
                slot_text,
                section_start=start,
                section_end=float(section_end),
                repeat=int(section["repeat"]),
            )
        return _parse_slot(
            slot_text,
            section_start=start,
            section_end=section_end,
            line_seconds=line_seconds,
            pace=str(section.get("pace", "sequential")),
        )
    return [
        (start + float(line.get("at", 0.0)), str(line["text"]))
        for line in section.get("lines", [])
    ]


def compose(
    template: dict[str, Any],
    slots: dict[str, str],
    *,
    title: str,
    document_id: str | None = None,
    line_seconds: float | None = None,
    duration: float | None = None,
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
        raise OCFError(f"unknown slot(s) for template {template['id']}: {', '.join(sorted(unknown))}")
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
    starts = [float(section.get("start", 0.0)) for section in template["sections"]]

    for index, section in enumerate(template["sections"]):
        slot_name = section.get("slot")
        section_end = starts[index + 1] if index + 1 < len(starts) else float(duration)
        events = resolve_section(
            section, slots, line_seconds=line_seconds, section_end=section_end
        )
        timeline: list[dict[str, Any]] = []
        for at_seconds, text in events:
            if at_seconds > duration:
                print(
                    f"Warning: {section['id']} event at {format_timestamp(at_seconds)} "
                    f"exceeds template duration {duration}s"
                )
            counter += 1
            timeline.append(
                {
                    "id": f"e{counter:03d}",
                    "at": format_timestamp(at_seconds),
                    "text": text,
                }
            )
        if slot_name and slot_name in slots:
            used_slots[slot_name] = [t for _, t in events]
        section_doc: dict[str, Any] = {"id": section["id"], "type": section["type"]}
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
            "version": template.get("schema_version"),
            "origin": template.get("origin", "original-ocf"),
        },
        "slots": used_slots,
    }
    template_source = template.get("source")
    if isinstance(template_source, dict):
        doc["source"] = dict(template_source)
    if document_id:
        doc["id"] = document_id

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