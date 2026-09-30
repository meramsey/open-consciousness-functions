"""Timed-transcript toolchain for OCF.

Implements the transcript pipeline specified in
``OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`` (§32,
§44–§46, §56–§57):

- parsing LRC (timed lyrics), SRT, WebVTT, and plain text/Markdown;
- normalizing into canonical **OCF timed YAML**;
- preserving the source text verbatim in an import snapshot (importers never
  silently rewrite wording);
- resolution of ``at`` / ``after``+``offset`` timelines with cycle detection;
- export back to SRT / VTT / LRC;
- structural analysis, section segmentation, and timing-only templates.

The module keeps its own CLI handlers (``run_transcript``) so
``ocf_tools/cli.py`` only has to wire the subcommand parser.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import AUDIO_SCRIPTS_DIR
from .utils import (
    OCFError,
    OCFFileExistsError,
    read_text,
    sha256_of_file,
    write_text_atomic,
    yaml_safe_load,
)

# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------


def parse_timestamp(value: str | None) -> float | None:
    """Parse a timestamp string into seconds.

    Accepts ``HH:MM:SS.mmm``, ``MM:SS.mmm``, ``MM:SS.xx``, and bare seconds.
    Name is misleadingly strict: fractional digits are optional and a comma
    is accepted as a decimal separator (SRT uses commas).
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            minutes, seconds = parts
            hours = 0
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            return None
        try:
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def format_timestamp(seconds: float | None) -> str | None:
    """Format seconds as canonical ``HH:MM:SS.mmm``."""
    if seconds is None:
        return None
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis_part = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis_part:03d}"


def format_srt_ts(seconds: float) -> str:
    """Format as SRT ``HH:MM:SS,mmm``."""
    canonical = format_timestamp(seconds)
    assert canonical is not None
    return canonical.replace(".", ",")


def format_lrc_ts(seconds: float) -> str:
    """Format as LRC ``MM:SS.xx`` (centiseconds)."""
    millis = int(round(seconds * 1000))
    minutes, rem = divmod(millis, 60_000)
    secs, millis_part = divmod(rem, 1000)
    return f"{minutes:02d}:{secs:02d}.{millis_part // 10:02d}"


# ---------------------------------------------------------------------------
# Parsed data model
# ---------------------------------------------------------------------------


@dataclass
class TranscriptEvent:
    """One timed (or untimed) narration segment from a source file."""

    text: str
    at: float | None = None  # absolute start in seconds; None = no timestamp
    ends_at: float | None = None  # exact source end time (SRT/VTT) if any
    cue_id: str | None = None  # VTT cue identifier, if any


@dataclass
class ParsedTranscript:
    """Normalized result of parsing one transcript file."""

    fmt: str
    events: list[TranscriptEvent]
    metadata: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    snapshot: str = ""
    filename: str = ""
    sha256: str = ""


@dataclass
class ResolvedEvent:
    """A timeline event resolved to absolute seconds (or flagged)."""

    id: str
    text: str
    at: float | None
    ends_at: float | None = None
    preferred_duration: float | None = None
    section: str | None = None
    cue_id: str | None = None


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_EXT_FORMATS = {
    ".lrc": "lrc",
    ".srt": "srt",
    ".vtt": "vtt",
    ".md": "md",
    ".markdown": "md",
    ".txt": "txt",
    ".yaml": "ocf-timed-yaml",
    ".yml": "ocf-timed-yaml",
}

_LRC_SNIFF = re.compile(r"^\[([0-9]{1,2}:[0-9]{1,2})([.,][0-9]{1,3})?\]", re.MULTILINE)
_SRT_SNIFF = re.compile(r"[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}\s*-->", re.MULTILINE)
_VTT_SNIFF = re.compile(r"[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}\s*-->", re.MULTILINE)


def _sniff_format(content: str) -> str | None:
    head = next((line for line in content.splitlines() if line.strip()), "")
    if head.upper().startswith("WEBVTT"):
        return "vtt"
    if _SRT_SNIFF.search(content):
        return "srt"
    if _VTT_SNIFF.search(content) or "-->" in content:
        return "vtt"
    if _LRC_SNIFF.search(content):
        return "lrc"
    return None


def detect_format(filename: str | None, content: str, explicit: str = "auto") -> str:
    """Resolve the transcript format by explicit choice, extension, or content."""
    if explicit and explicit != "auto":
        return explicit
    ext = Path(filename or "").suffix.lower()
    if ext in _EXT_FORMATS and ext not in (".txt",):
        return _EXT_FORMATS[ext]
    sniffed = _sniff_format(content)
    if sniffed:
        return sniffed
    if ext in _EXT_FORMATS:
        return _EXT_FORMATS[ext]
    return "txt"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _leading_brackets(line: str) -> tuple[list[str], str]:
    """Split leading ``[token]`` groups from the rest of an LRC-style line."""
    tokens: list[str] = []
    index = 0
    while line.startswith("[", index):
        end = line.find("]", index)
        if end == -1:
            break
        tokens.append(line[index + 1 : end])
        index = end + 1
    return tokens, line[index:]


def parse_lrc(text: str) -> ParsedTranscript:
    """Parse an LRC (timed-lyrics) file into a ParsedTranscript."""
    events: list[TranscriptEvent] = []
    metadata: dict[str, str] = {}
    notes: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        tokens, rest = _leading_brackets(raw)
        if not tokens:
            if rest.strip():
                notes.append(f"line {lineno}: line without a timestamp bracket was skipped")
            continue
        times: list[float] = []
        for token in tokens:
            parsed = parse_timestamp(token)
            if parsed is not None:
                times.append(parsed)
            elif ":" in token:
                key, _, value = token.partition(":")
                key = key.strip()
                if key in metadata and metadata[key] != value:
                    metadata[key] = f"{metadata[key]}; {value}"
                else:
                    metadata[key] = value
            else:
                notes.append(f"line {lineno}: unrecognized tag '[{token}]'")
        if not times:
            if rest.strip():
                notes.append(f"line {lineno}: bracket tag without a timestamp was skipped")
            continue
        for t in times:
            events.append(TranscriptEvent(text=rest, at=t))
    events.sort(key=lambda event: event.at)
    return ParsedTranscript(fmt="lrc", events=events, metadata=metadata, notes=notes, snapshot=text)


_SRT_CUE = re.compile(
    r"^(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})"
)


def parse_srt(text: str) -> ParsedTranscript:
    """Parse an SRT subtitle file into a ParsedTranscript."""
    events: list[TranscriptEvent] = []
    notes: list[str] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for block_index, block in enumerate(re.split(r"\n[ \t]*\n", normalized), start=1):
        if not block.strip():
            continue
        lines = block.split("\n")
        cue_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if cue_idx is None:
            notes.append(f"block {block_index}: no timing line; skipped")
            continue
        match = _SRT_CUE.match(lines[cue_idx].strip())
        if not match:
            notes.append(f"block {block_index}: unparsed timing line; skipped")
            continue
        start = (
            int(match.group(1)) * 3600
            + int(match.group(2)) * 60
            + int(match.group(3))
            + int(match.group(4)) / 1000
        )
        end = (
            int(match.group(5)) * 3600
            + int(match.group(6)) * 60
            + int(match.group(7))
            + int(match.group(8)) / 1000
        )
        events.append(TranscriptEvent(text="\n".join(lines[cue_idx + 1 :]), at=start, ends_at=end))
    return ParsedTranscript(fmt="srt", events=events, notes=notes, snapshot=text)


_VTT_CUE = re.compile(
    r"^((?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*"
    r"((?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3})"
)


def _vtt_time(marker: str) -> float:
    value = parse_timestamp(marker)
    if value is None:
        raise ValueError(f"unparseable VTT timestamp: {marker}")
    return value


def parse_vtt(text: str) -> ParsedTranscript:
    """Parse a WebVTT file into a ParsedTranscript."""
    events: list[TranscriptEvent] = []
    notes: list[str] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.startswith("\ufeff"):
        normalized = normalized[1:]
    first = next((line for line in normalized.splitlines() if line.strip()), "")
    if first.upper().startswith("WEBVTT"):
        normalized = normalized.split("\n", 1)[1]
    for block_index, block in enumerate(re.split(r"\n[ \t]*\n", normalized), start=1):
        stripped = block.strip()
        if not stripped:
            continue
        lowered = stripped.lstrip()
        if lowered.upper().startswith(("NOTE", "STYLE", "REGION")):
            notes.append(stripped)
            continue
        lines = stripped.split("\n")
        cue_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if cue_idx is None:
            notes.append(f"block {block_index}: no timing line; skipped")
            continue
        match = _VTT_CUE.match(lines[cue_idx].strip())
        if not match:
            notes.append(f"block {block_index}: unparsed timing line; skipped")
            continue
        cue_id = lines[cue_idx - 1].strip() or None if cue_idx >= 1 else None
        events.append(
            TranscriptEvent(
                text="\n".join(lines[cue_idx + 1 :]),
                at=_vtt_time(match.group(1)),
                ends_at=_vtt_time(match.group(2)),
                cue_id=cue_id,
            )
        )
    return ParsedTranscript(fmt="vtt", events=events, notes=notes, snapshot=text)


def parse_plain(text: str, fmt: str) -> ParsedTranscript:
    """Parse an untimed ``txt``/``md`` transcript into paragraph events."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    events: list[TranscriptEvent] = []
    for paragraph in re.split(r"\n[ \t]*\n", normalized):
        paragraph = paragraph.strip()
        if paragraph:
            events.append(TranscriptEvent(text=paragraph, at=None))
    return ParsedTranscript(fmt=fmt, events=events, snapshot=text)


def parse_transcript(
    text: str, *, fmt: str, filename: str = "", sha256: str = ""
) -> ParsedTranscript:
    """Parse text in the given format into a normalized transcript."""
    if fmt == "lrc":
        parsed = parse_lrc(text)
    elif fmt == "srt":
        parsed = parse_srt(text)
    elif fmt == "vtt":
        parsed = parse_vtt(text)
    elif fmt in ("txt", "md"):
        parsed = parse_plain(text, fmt)
    else:
        raise OCFError(f"format '{fmt}' is not importable (expected lrc/srt/vtt/txt/md)")
    parsed.filename = filename
    parsed.sha256 = sha256
    return parsed


# ---------------------------------------------------------------------------
# Canonical OCF timed YAML
# ---------------------------------------------------------------------------


class _LiteralDumper(yaml.SafeDumper):
    """SafeDumper that renders multiline strings as YAML literal blocks."""


def _represent_str(dumper: _LiteralDumper, data: str) -> yaml.Node:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_LiteralDumper.add_representer(str, _represent_str)


def dump_timed_yaml(doc: dict) -> str:
    """Serialize a timed-transcript document deterministically."""
    return yaml.dump(
        doc,
        Dumper=_LiteralDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=100,
    )


def timed_yaml_doc(parsed: ParsedTranscript, title: str | None = None) -> dict:
    """Build a canonical OCF timed-YAML document from a parsed transcript."""
    if title is None:
        title = parsed.metadata.get("ti") or Path(parsed.filename).stem or "Untitled transcript"
    timeline: list[dict] = []
    for index, event in enumerate(parsed.events, start=1):
        entry: dict = {"id": f"e{index:03d}", "text": event.text}
        entry["at"] = format_timestamp(event.at)
        if event.ends_at is not None:
            entry["ends_at"] = format_timestamp(event.ends_at)
        if event.cue_id:
            entry["cue_id"] = event.cue_id
        # Stable order for untimed imports: preserve source order.
        timeline.append(entry)
    timeline.sort(key=lambda e: (e["at"] is None, parse_timestamp(e["at"]) or 0.0))
    source: dict = {"format": parsed.fmt, "filename": parsed.filename}
    if parsed.sha256:
        source["sha256"] = parsed.sha256
    if parsed.metadata:
        source["metadata"] = dict(parsed.metadata)
    if parsed.notes:
        source["notes"] = list(parsed.notes)
    if parsed.snapshot is not None:
        source["snapshot"] = parsed.snapshot
    return {"schema_version": "1.0", "title": title, "source": source, "timeline": timeline}


def load_timed_doc(path: str | Path) -> dict:
    """Load a canonical OCF timed-YAML document from disk."""
    data = yaml_safe_load(read_text(Path(path)))
    if not isinstance(data, dict):
        raise OCFError(f"{path} is not an OCF timed-transcript document (expected a mapping)")
    return data


def write_timed_doc(path: str | Path, doc: dict, *, overwrite: bool = True) -> None:
    """Write a timed-transcript document atomically."""
    try:
        write_text_atomic(Path(path), dump_timed_yaml(doc), overwrite=overwrite)
    except OCFFileExistsError as exc:
        raise OCFError(f"{exc} (use --force to overwrite)") from exc


# ---------------------------------------------------------------------------
# Timeline resolution
# ---------------------------------------------------------------------------


def resolve_timeline(doc: dict) -> tuple[list[ResolvedEvent], list[str]]:
    """Resolve a timed document into absolute-time events.

    Supports a flat top-level ``timeline`` or section-grouped transcripts.
    ``after`` references are resolved within their own timeline only; circular
    references and unknown targets are reported as problems (never guessed).
    """
    problems: list[str] = []
    events: list[ResolvedEvent] = []

    sections = doc.get("sections")
    timeline = doc.get("timeline")
    if sections is not None and timeline is not None:
        problems.append("document has both 'timeline' and 'sections'; use only one")

    if sections is not None:
        seen_sections: set[str] = set()
        for section in sections:
            section_id = section.get("id")
            if section_id in seen_sections:
                problems.append(f"duplicate section id '{section_id}'")
            seen_sections.add(section_id)
            events.extend(_resolve_event_list(section.get("timeline", []), section_id, problems))
    if timeline is not None:
        events.extend(_resolve_event_list(timeline, None, problems))
    return events, problems


def _resolve_event_list(
    events: list[dict], section: str | None, problems: list[str]
) -> list[ResolvedEvent]:
    by_id: dict[str, dict] = {}
    seen: set[str] = set()
    for event in events:
        event_id = event.get("id")
        if event_id in seen:
            problems.append(f"duplicate event id '{event_id}'")
        seen.add(event_id)
        by_id[event_id] = event

    memo: dict[str, float | None] = {}
    path: list[str] = []

    def absolute(event: dict) -> float | None:
        event_id = event.get("id")
        if event_id in memo:
            return memo[event_id]
        if event_id in path:
            cycle_start = path.index(event_id)
            problems.append(
                "circular 'after' reference: " + " -> ".join(path[cycle_start:] + [event_id])
            )
            return None
        at = event.get("at")
        if at is not None:
            value = parse_timestamp(str(at))
            if value is None:
                problems.append(f"event '{event_id}' has unparseable 'at': {at!r}")
                value = 0.0
        elif "after" in event:
            target = event.get("after")
            if target not in by_id:
                problems.append(f"event '{event_id}' references unknown 'after' target '{target}'")
                value = None
            else:
                path.append(event_id)
                base = absolute(by_id[target])
                path.pop()
                offset = event.get("offset")
                if not isinstance(offset, (int, float)):
                    offset = 0.0
                value = base + offset if base is not None else None
        else:
            value = None  # untimed / unassigned
        memo[event_id] = value
        return value

    for event in events:
        absolute(event)

    resolved: list[ResolvedEvent] = []
    for event in events:
        event_id = event.get("id")
        timing = event.get("timing") or {}
        preferred = timing.get("preferred_duration")
        ends_at = (
            parse_timestamp(str(event.get("ends_at"))) if event.get("ends_at") is not None else None
        )
        resolved.append(
            ResolvedEvent(
                id=event_id,
                text=event.get("text", ""),
                at=memo.get(event_id),
                ends_at=ends_at,
                preferred_duration=float(preferred)
                if isinstance(preferred, (int, float))
                else None,
                section=section,
                cue_id=event.get("cue_id"),
            )
        )
    return resolved


def estimate_duration(events: list[ResolvedEvent], index: int) -> float:
    """Best-effort duration for an export cue (estimates, never exact)."""
    event = events[index]
    if event.at is None:
        return 3.0
    if event.ends_at is not None:
        return max(0.2, event.ends_at - event.at)
    if event.preferred_duration is not None:
        return max(0.2, event.preferred_duration)
    for nxt in events[index + 1 :]:
        if nxt.at is not None:
            gap = nxt.at - event.at
            if gap >= 0.5:
                return gap
            break
    return 4.0


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _export_events(doc: dict) -> list[ResolvedEvent]:
    events, problems = resolve_timeline(doc)
    untimed = [e for e in events if e.at is None]
    if untimed:
        raise OCFError(
            f"cannot export: {len(untimed)} event(s) have no timestamp "
            "(import a timed format, then re-export)"
        )
    if problems:
        raise OCFError("timeline problems; fix before exporting: " + " | ".join(problems[:3]))
    return sorted(events, key=lambda e: e.at or 0.0)


def export_srt(doc: dict) -> str:
    """Convert a timed document to SRT subtitle text."""
    events = _export_events(doc)
    cues: list[str] = []
    for index, event in enumerate(events, start=1):
        end = event.at + estimate_duration(events, index - 1)
        cues.append(f"{index}\n{format_srt_ts(event.at)} --> {format_srt_ts(end)}\n{event.text}")
    return "\n\n".join(cues) + "\n"


def export_vtt(doc: dict) -> str:
    """Convert a timed document to WebVTT text."""
    events = _export_events(doc)
    cues: list[str] = ["WEBVTT", ""]
    for index, event in enumerate(events, start=1):
        end = event.at + estimate_duration(events, index - 1)
        start_ts = format_timestamp(event.at)
        cue = f"{start_ts} --> {format_timestamp(end)}"
        if event.cue_id:
            cue = f"{event.cue_id}\n{cue}"
        cue += f"\n{event.text}"
        cues.append(cue)
    return "\n\n".join(cues) + "\n"


def export_lrc(doc: dict) -> str:
    """Convert a timed document to LRC (timed-lyrics) text."""
    events = _export_events(doc)
    lines: list[str] = []
    for event in events:
        text = event.text.replace("\n", " ")
        lines.append(f"[{format_lrc_ts(event.at)}]{text}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Structural analysis (heuristics, always labeled as suggestions)
# ---------------------------------------------------------------------------

_STATE_WORDS = (
    "state",
    "focus",
    "access",
    "entering",
    "entered",
    "level",
    "awaken",
    "awake",
    "open",
    "close",
    "closed",
    "return",
    "returning",
    "count",
    "learn",
    "install",
    "rehearse",
    "practice",
)
_LONG_PAUSE_SECONDS = 12.0


def is_countdown(text: str) -> bool:
    """True if a line looks like a numeric countdown (a suggestion, not a fact)."""
    numbers = [int(tok) for tok in re.findall(r"\d{1,2}", text)]
    if len(numbers) < 3:
        return False
    descending = all(numbers[i] <= numbers[i - 1] + 1 for i in range(1, len(numbers)))
    ascending = all(numbers[i] + 1 >= numbers[i - 1] for i in range(1, len(numbers)))
    return descending or ascending


def state_cue_score(text: str) -> int:
    """Count state/focus transition cue words in a line."""
    lowered = text.lower()
    return sum(lowered.count(word.lower()) for word in _STATE_WORDS)


def suggest_boundaries(events: list[ResolvedEvent]) -> list[dict]:
    """Suggest candidate section boundaries (label everything as suggestion)."""
    timed = sorted((e for e in events if e.at is not None), key=lambda e: e.at or 0.0)
    suggestions: list[dict] = []
    previous: ResolvedEvent | None = None
    for position, event in enumerate(timed):
        reasons: list[str] = []
        if is_countdown(event.text):
            reasons.append("countdown")
        if state_cue_score(event.text) >= 2:
            reasons.append("state-cue")
        if previous is not None:
            prev_end = previous.ends_at if previous.ends_at is not None else previous.at
            gap = (event.at or 0.0) - (prev_end or 0.0)
            if gap >= _LONG_PAUSE_SECONDS:
                reasons.append(f"long pause ({gap:.0f}s)")
        if reasons:
            suggestions.append(
                {
                    "position": position,
                    "at": event.at,
                    "text": event.text[:70],
                    "reasons": reasons,
                }
            )
        previous = event
    return suggestions


def guess_section_type(text: str) -> str:
    """Best-effort section role for an event (a suggestion, always editable)."""
    lowered = text.lower()
    if is_countdown(text) or state_cue_score(text) >= 3:
        return "state-transition"
    for word in ("access", "open"):
        if word in lowered:
            return "access-open"
    for word in ("install", "learn", "command", "plus"):
        if word in lowered:
            return "installation"
    for word in ("rehearse", "rehearsal", "practice", "repeat"):
        if word in lowered:
            return "rehearsal"
    if any(word in lowered for word in ("return", "wake", "close")):
        return "return"
    if any(word in lowered for word in ("settle", "relax", "breath", "prepar")):
        return "preparation"
    return "freeform"


def flatten_event_dicts(doc: dict) -> list[tuple[str | None, dict]]:
    """Return (section_id, event_dict) for every event in document order."""
    flattened: list[tuple[str | None, dict]] = []
    sections = doc.get("sections")
    if sections is not None:
        for section in sections:
            section_id = section.get("id")
            for event in section.get("timeline", []):
                flattened.append((section_id, event))
    else:
        for event in doc.get("timeline", []):
            flattened.append((None, event))
    return flattened


def apply_sections(doc: dict, boundary_indices: list[int]) -> dict:
    """Group the timeline into sections, cutting at the given positions.

    `boundary_indices` are positions into the ordered list of timed events
    (as produced by ``suggest_boundaries``). Content is never rewritten;
    events merely get grouped into new section roles.
    """
    flattened = flatten_event_dicts(doc)
    timed_positions = [
        idx for idx, (_section, event) in enumerate(flattened) if event.get("at") is not None
    ]
    cut_events: set[int] = set()
    for boundary in boundary_indices:
        if 0 <= boundary < len(timed_positions):
            cut_events.add(timed_positions[boundary])

    sections: list[dict] = []
    current: list[dict] = []
    for index, (_section, event) in enumerate(flattened):
        if index in cut_events and current:
            sections.append(
                {
                    "id": f"sec-{len(sections) + 1:03d}",
                    "type": guess_section_type(current[0].get("text", "")),
                    "timeline": current,
                }
            )
            current = []
        current.append(event)
    if current:
        sections.append(
            {
                "id": f"sec-{len(sections) + 1:03d}",
                "type": guess_section_type(current[0].get("text", "")),
                "timeline": current,
            }
        )
    updated = dict(doc)
    updated.pop("timeline", None)
    updated["sections"] = sections
    return updated


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze_transcript(doc: dict) -> dict:
    """Produce a structural analysis. Every finding is labeled a suggestion."""
    events, problems = resolve_timeline(doc)
    timed = sorted((e for e in events if e.at is not None), key=lambda e: e.at or 0.0)

    silences: list[dict] = []
    previous: ResolvedEvent | None = None
    for event in timed:
        if previous is not None and previous.at is not None and event.at is not None:
            prev_end = previous.ends_at if previous.ends_at is not None else previous.at
            gap = event.at - prev_end
            if gap >= _LONG_PAUSE_SECONDS:
                silences.append({"at": event.at, "seconds": gap, "after": previous.text[:40]})
        previous = event

    countdowns = [e for e in timed if is_countdown(e.text)]
    state_cues = [e for e in timed if state_cue_score(e.text) >= 2]

    normalized = [re.sub(r"\s+", " ", e.text.strip().lower()) for e in events]
    repeats: dict[str, list[int]] = {}
    for index, text in enumerate(normalized):
        if len(text) >= 12:
            repeats.setdefault(text, []).append(index)
    repeated = [
        {"text": text, "count": len(idx), "indices": idx[:3]}
        for text, idx in repeats.items()
        if len(idx) > 1
    ]

    boundaries = suggest_boundaries(events)
    return {
        "problems": problems,
        "entries": len(events),
        "timed_entries": len(timed),
        "untimed_entries": len(events) - len(timed),
        "total_duration_seconds": timed[-1].at if timed else None,
        "silences": silences[:5],
        "silence_count": len(silences),
        "countdowns": countdowns,
        "state_cues": state_cues,
        "repeated": repeated,
        "boundaries": boundaries,
    }


def format_analysis(analysis: dict) -> str:
    """Render an analysis dict as human-readable text."""
    duration = analysis["total_duration_seconds"]
    lines = [
        f"entries: {analysis['entries']} "
        f"({analysis['timed_entries']} timed, {analysis['untimed_entries']} untimed)",
        f"total duration: {format_timestamp(duration) if duration is not None else 'n/a'}",
    ]
    if analysis["problems"]:
        lines.append("timeline problems:")
        lines.extend(f"  - {problem}" for problem in analysis["problems"][:10])
    lines.append(f"suggested boundaries: {len(analysis['boundaries'])}")
    for boundary in analysis["boundaries"]:
        at = format_timestamp(boundary["at"])
        lines.append(f"  - {at} [{'/'.join(boundary['reasons'])}]: {boundary['text']!r}")
    if analysis["silences"]:
        lines.append(f"longest pauses ({len(analysis['silences'])} suggestion(s)):")
        for silence in analysis["silences"][:5]:
            lines.append(
                f"  - {silence['seconds']:.0f}s before {format_timestamp(silence['at'])} "
                f"({silence['after']!r})"
            )
    if analysis["countdowns"]:
        lines.append("possible countdowns (suggestions):")
        for event in analysis["countdowns"][:8]:
            lines.append(f"  - {format_timestamp(event.at)}: {event.text[:60]!r}")
    if analysis["state_cues"]:
        lines.append("possible state-transition cues (suggestions):")
        for event in analysis["state_cues"][:8]:
            lines.append(f"  - {format_timestamp(event.at)}: {event.text[:60]!r}")
    if analysis["repeated"]:
        lines.append("repeated passages (suggestions):")
        for repeat in analysis["repeated"][:8]:
            lines.append(f"  - x{repeat['count']}: {repeat['text'][:60]!r}")
    if not (
        analysis["boundaries"]
        or analysis["silences"]
        or analysis["countdowns"]
        or analysis["state_cues"]
        or analysis["repeated"]
    ):
        lines.append("no structural suggestions detected.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Timing-only template extraction
# ---------------------------------------------------------------------------


def extract_timing_template(doc: dict, title: str | None = None) -> dict:
    """Build a timing-only structural template (no transcript text)."""
    events, problems = resolve_timeline(doc)
    timed = sorted((e for e in events if e.at is not None), key=lambda e: e.at or 0.0)
    boundary_positions = [b["position"] for b in suggest_boundaries(events)]

    spans: list[tuple[int, int, str]] = []
    start = 0
    for position in boundary_positions:
        if position > start:
            spans.append((start, position, guess_section_type(timed[start].text)))
        start = position
    if start < len(timed):
        spans.append((start, len(timed), guess_section_type(timed[start].text)))

    template_sections: list[dict] = []
    for index, (start, end, section_type) in enumerate(spans, start=1):
        first = timed[start]
        last = timed[end - 1]
        end_at = last.ends_at if last.ends_at is not None else last.at
        template_sections.append(
            {
                "id": f"tpl-{index:03d}",
                "type": section_type,
                "start": format_timestamp(first.at),
                "end": format_timestamp(end_at),
                "text": None,
            }
        )
    doc_title = title or f"{Path(doc.get('title', 'transcript')).stem} (timing template)"
    return {
        "schema_version": "1.0",
        "title": doc_title,
        "source": {
            "format": "ocf-timed-yaml",
            "filename": doc.get("source", {}).get("filename"),
            "sha256": doc.get("source", {}).get("sha256"),
            "notes": ["timing-only template: no transcript text is included"],
        },
        "sections": template_sections,
    }


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------


def _default_import_output(path: str) -> Path:
    return AUDIO_SCRIPTS_DIR / f"{Path(path).stem}.yaml"


def _print_import_summary(parsed: ParsedTranscript, output: Path) -> None:
    duration = None
    timed = [e for e in parsed.events if e.at is not None]
    if timed:
        duration = format_timestamp(max(e.at for e in timed))
    summary = f"Imported {len(parsed.events)} entr{'y' if len(parsed.events) == 1 else 'ies'}"
    if duration:
        summary += f" (duration {duration})"
    print(f"{summary} from {parsed.filename} as {parsed.fmt.upper()}.")
    if parsed.notes:
        print(f"Note: {len(parsed.notes)} import note(s); source snapshot retained verbatim.")
    print(f"Wrote {output}")
    print("Next steps:")
    print(f"  ocf transcript segment {output}        # assign section roles")
    print(f"  ocf transcript analyze {output} --interactive   # review suggested boundaries")
    print(f"  ocf transcript review {output}        # validate and summarize")


def run_import(args) -> int:
    """`ocf transcript import` — parse a source file into OCF timed YAML."""
    try:
        raw = read_text(Path(args.file))
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    fmt = detect_format(args.file, raw, getattr(args, "format", "auto"))
    if fmt == "ocf-timed-yaml":
        print(f"{args.file} is already canonical OCF timed YAML; validating …")
        return _validate_file(args.file)

    sha = sha256_of_file(Path(args.file))
    parsed = parse_transcript(raw, fmt=fmt, filename=Path(args.file).name, sha256=sha)
    if not parsed.events:
        print(f"error: no timed entries found in {args.file}", file=sys.stderr)
        return 1

    doc = timed_yaml_doc(parsed, getattr(args, "title", None))
    if getattr(args, "output", None):
        output = Path(args.output)
    else:
        output = _default_import_output(args.file)
    try:
        write_timed_doc(output, doc, overwrite=bool(getattr(args, "force", False)))
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    status = _validate_file(str(output))
    if status == 0:
        _print_import_summary(parsed, output)
    return status


def _validate_file(path: str) -> int:
    from .validators import print_result, validate_timed_transcript_file

    return print_result(validate_timed_transcript_file(Path(path)))


def run_analyze(args) -> int:
    """`ocf transcript analyze [--interactive]` — structural analysis."""
    try:
        doc = load_timed_doc(args.file)
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    analysis = analyze_transcript(doc)
    print(format_analysis(analysis))
    print("\nAll findings are suggestions, not a semantic classifier.")
    if getattr(args, "interactive", False):
        return _segment_interactive_flow(args.file, doc, apply_all=False)
    return 0


def run_segment(args) -> int:
    """`ocf transcript segment [--apply]` — group the timeline into sections."""
    try:
        doc = load_timed_doc(args.file)
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "apply", False):
        return _segment_apply_flow(
            args.file,
            doc,
            output=getattr(args, "output", None),
            force=bool(getattr(args, "force", False)),
        )
    return _segment_interactive_flow(args.file, doc, apply_all=False)


def _segment_apply_flow(
    path: str, doc: dict, *, output: str | None = None, force: bool = False
) -> int:
    events, _problems = resolve_timeline(doc)
    boundaries = suggest_boundaries(events)
    if not boundaries:
        print("No suggested boundaries found; the timeline is already one section.")
        return 0
    updated = apply_sections(doc, [b["position"] for b in boundaries])
    _write_or_print(path, updated, output, force=force)
    print(
        f"Applied {len(boundaries)} suggested boundary/boundaries "
        "(suggestions — review with `ocf transcript review`)."
    )
    return _validate_file(path)


def _segment_interactive_flow(path: str, doc: dict, *, apply_all: bool) -> int:
    events, _problems = resolve_timeline(doc)
    boundaries = suggest_boundaries(events)
    if not boundaries:
        print("No suggested boundaries found.")
        return 0
    accepted: list[int] = []
    for boundary in boundaries:
        at = format_timestamp(boundary["at"])
        label = f"{at} [{', '.join(boundary['reasons'])}] {boundary['text']!r}"
        answer = input(f"Start a new section at {label}? (y/n) ").strip().lower()
        if answer in ("y", "yes"):
            accepted.append(boundary["position"])
    if not accepted:
        print("No sections assigned; nothing changed.")
        return 0
    updated = apply_sections(doc, accepted)
    overwrite = input(f"Write sections back to {path}? (y/n) ").strip().lower()
    if overwrite not in ("y", "yes"):
        print("Section assignment discarded.")
        return 0
    write_timed_doc(path, updated, overwrite=True)
    print(f"Wrote {len(updated['sections'])} section(s) to {path}.")
    return _validate_file(path)


def run_review(args) -> int:
    """`ocf transcript review [--state-profile NAME] [--write] [--output PATH]`."""
    try:
        doc = load_timed_doc(args.file)
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    status = _validate_file(args.file)
    analysis = analyze_transcript(doc)
    print()
    print(format_analysis(analysis))

    changed = False
    profile = getattr(args, "state_profile", None)
    if profile:
        doc["state_profile"] = profile
        changed = True
        print(f"state_profile set to {profile!r}")

    output = getattr(args, "output", None)
    if changed and (output or getattr(args, "write", False)):
        target = Path(output) if output else Path(args.file)
        write_timed_doc(target, doc, overwrite=bool(getattr(args, "force", False)))
        print(f"Wrote {target}")
    elif changed:
        print("Changed in memory only; pass --write or --output to save.")
    return status


def run_export(args) -> int:
    """`ocf transcript export FILE --format srt|vtt|lrc`."""
    try:
        doc = load_timed_doc(args.file)
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    exporter = {"srt": export_srt, "vtt": export_vtt, "lrc": export_lrc}.get(args.format)
    if exporter is None:
        print(f"error: unsupported export format {args.format!r}", file=sys.stderr)
        return 1
    try:
        content = exporter(doc)
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "output", None):
        output = Path(args.output)
        try:
            write_text_atomic(output, content, overwrite=bool(getattr(args, "force", False)))
        except OCFFileExistsError as exc:
            print(f"error: {exc} (use --force to overwrite)", file=sys.stderr)
            return 1
        print(f"Wrote {output}")
    else:
        print(content, end="")
    return 0


def run_extract_template(args) -> int:
    """`ocf transcript extract-template FILE --timing-only`."""
    try:
        doc = load_timed_doc(args.file)
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    template = extract_timing_template(doc)
    if getattr(args, "output", None):
        output = Path(args.output)
        write_timed_doc(output, template, overwrite=bool(getattr(args, "force", False)))
        print(f"Wrote timing-only template to {output}")
    else:
        print(dump_timed_yaml(template), end="")
    return 0


def _write_or_print(path: str, doc: dict, output: str | None, *, force: bool) -> None:
    target = Path(output) if output else Path(path)
    write_timed_doc(target, doc, overwrite=force or bool(output is None))


def run_transcript(args) -> int:
    """Route `transcript` subcommands to their handlers."""
    handler = {
        "import": run_import,
        "analyze": run_analyze,
        "segment": run_segment,
        "review": run_review,
        "export": run_export,
        "extract-template": run_extract_template,
    }.get(getattr(args, "transcript_kind", None))
    if handler is None:
        help_text("ocf transcript import|analyze|segment|review|export|extract-template")
        return 0
    return handler(args)


def help_text(commands: str) -> None:
    print("Open Consciousness Functions — timed-transcript tooling.")
    print(f"Usage: {commands}")
