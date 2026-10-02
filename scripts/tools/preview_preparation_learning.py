"""Generate Preparation Learning text-only review views; never invokes audio engines."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from ocf_tools.locale import LocaleCatalog, iter_events, resolve_document  # noqa: E402
from ocf_tools.semantics import bind_document_cues  # noqa: E402
from ocf_tools.session import compose, load_template  # noqa: E402
from ocf_tools.timing import schedule_timeline  # noqa: E402
from ocf_tools.transcript import format_timestamp  # noqa: E402
from ocf_tools.utils import OCFError  # noqa: E402
from ocf_tools.validators import validate_timed_transcript  # noqa: E402

BANNER = "<!-- GENERATED TEXT-ONLY REVIEW PREVIEW; edit locale/stage/template sources, then regenerate. -->"
WORD = re.compile(r"\b\w+(?:['’-]\w+)*\b")


def build_preview(
    *, include_optional: bool = True, affirmation: str | None = None, words_per_minute: float = 140
) -> dict:
    """Resolve original en-US words and estimate duration, without synthetic audio."""
    if words_per_minute <= 0:
        raise OCFError("preview words per minute must be positive")
    if affirmation and not include_optional:
        raise OCFError("configured affirmation requires the optional stages to be enabled")
    template = load_template("OCF-TPL-SESSION-PREP-LEARN-001")
    if affirmation:
        section = next(
            section for section in template["sections"] if section["id"] == "affirmation"
        )
        section["narration"]["practice"] = {
            "narration_key": "preparation.affirmation.words",
            "variables": {"affirmation": affirmation},
        }
    doc = compose(
        template,
        {},
        title=template["name"],
        enabled_stages=["affirmation", "tuning"] if include_optional else [],
    )
    resolved = resolve_document(doc, "en-US", strict=True)
    validation = validate_timed_transcript(resolved, Path("text-only-preview"))
    if validation.errors:
        raise OCFError(" | ".join(issue.message for issue in validation.errors))
    events = list(iter_events(resolved))
    words = {event["id"]: len(WORD.findall(event.get("text", ""))) for event in events}
    estimates = {
        identifier: count * 60 / words_per_minute for identifier, count in words.items() if count
    }
    schedule = schedule_timeline(resolved, estimates)
    by_id = {event["id"]: event for event in events}
    ordered = [by_id[row["id"]] for row in schedule]
    stats = {
        "spoken_words": sum(words.values()),
        "words_per_minute": words_per_minute,
        "estimated_speech_s": sum(estimates.values()),
        "explicit_pause_s": sum(
            float((event.get("timing") or {}).get("pause_after", 0)) for event in events
        ),
        "estimated_session_s": max((row["end"] for row in schedule), default=0),
        "optional_stages": include_optional,
    }
    listener = [
        BANNER,
        "# OCF Preparation Learning en-US RC1 — listener transcript",
        "",
        "Approved narration/semantic release candidate, not production audio. Optional affirmation and tuning are "
        + ("included below" if include_optional else "omitted")
        + "; no default affirmation, tone, or cue sound is selected.",
        "",
    ]
    listener.extend(event["text"] + "\n" for event in ordered if event.get("text", "").strip())
    developer = [
        BANNER,
        "# OCF Preparation Learning en-US RC1 — developer view",
        "",
        "All clock times below are **estimates**, not measured TTS or production anchors. "
        "Event dependencies and pauses remain the authored semantic data. "
        "Cue bindings are disabled/TBD; no audio was generated.",
        "",
        f"- Spoken words: {stats['spoken_words']}",
        f"- Estimate rate: {words_per_minute:g} words/minute",
        f"- Estimated speech: {stats['estimated_speech_s'] / 60:.2f} minutes",
        f"- Explicit pauses: {stats['explicit_pause_s']:g} seconds",
        f"- Estimated total: {stats['estimated_session_s'] / 60:.2f} minutes",
        "",
        "| Estimated start | Event / semantic identity | Narration key | Anchor | Pause after | DSP | Auditory reference |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in schedule:
        event = by_id[row["id"]]
        timing = event.get("timing") or {}
        pause = float(timing.get("pause_after", 0))
        category = "brief" if pause <= 5 else "experiential" if pause <= 20 else "practice"
        anchor = (
            f"{event['after']} / {timing.get('anchor', 'start')}"
            if event.get("after")
            else "session start"
        )
        developer.append(
            f"| {format_timestamp(row['at'])} | `{event['id']}` / `{event.get('semantic', '')}` "
            f"| `{event.get('narration_key', '—')}` | {anchor} "
            f"| {pause:g}s ({category}) | {event.get('dsp', '—')} "
            f"| `{event.get('auditory_cue', '—')}` |"
        )
    developer.extend(["", "## Cue bindings", ""])
    for binding in bind_document_cues(resolved):
        developer.append(
            f"- `{binding['event_id']}` → `{binding['identity']}`: {binding['binding']['mode']} (sound design TBD)"
        )
    developer.extend(
        [
            "",
            "## Resource inventory",
            "",
            "Fixed RC1 resources are reviewed; unused/general or custom-content slots retain their own status. "
            "Configured affirmation wording is not assigned by default.",
            "",
        ]
    )
    catalog = LocaleCatalog()
    for key, resource in sorted(catalog.canonical.entries.items()):
        if resource.file == "preparation-learning.yaml" or key.startswith("function.learning."):
            developer.append(
                f"- `{key}` — `{resource.file}`, v{resource.version}, {resource.status}: {resource.notes}"
            )
    return {
        "document": resolved,
        "stats": stats,
        "listener": "\n".join(listener).rstrip() + "\n",
        "developer": "\n".join(developer).rstrip() + "\n",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "drafts")
    parser.add_argument("--without-optional", action="store_true")
    parser.add_argument(
        "--affirmation", help="explicit en-US review wording, not a universal default"
    )
    parser.add_argument("--words-per-minute", type=float, default=140)
    parser.add_argument(
        "--check", action="store_true", help="check preview freshness without writing"
    )
    args = parser.parse_args(argv)
    try:
        preview = build_preview(
            include_optional=not args.without_optional,
            affirmation=args.affirmation,
            words_per_minute=args.words_per_minute,
        )
        for name in ("listener", "developer"):
            path = args.output_dir / f"preparation-learning.en-US.{name}.md"
            if args.check:
                if not path.is_file() or path.read_text(encoding="utf-8") != preview[name]:
                    raise OCFError(f"text preview is stale: {path}")
            else:
                if path.exists() and not path.read_text(encoding="utf-8").startswith(BANNER):
                    raise OCFError(f"refusing to overwrite an unrelated file: {path}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(preview[name], encoding="utf-8")
        print(preview["stats"])
        return 0
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
