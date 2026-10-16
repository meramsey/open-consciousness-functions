"""CLI and reusable import services for explicit private narration sources."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .indexes import load_yaml_file
from .locale import iter_events, resolve_document
from .narration_sources import SourceResolver, text_fingerprint
from .utils import OCFError, sha256_of_file, write_text_atomic


def add_commands(subparsers):
    parser = subparsers.add_parser(
        "narration",
        help="recorded/hybrid narration sources, technical inspection and measured assembly",
    )
    commands = parser.add_subparsers(dest="narration_kind", required=True)
    for name in ("sources", "preview", "validate"):
        command = commands.add_parser(
            name, help="inspect explicit cue source coverage and text compatibility"
        )
        command.add_argument("function_id")
        command.add_argument("--sources", type=Path)
        command.add_argument("--locale", default="en-US")
    init = commands.add_parser(
        "init", help="create a private source manifest without fabricating recordings"
    )
    init.add_argument("function_id")
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--mode", choices=("recording", "hybrid", "tts"), default="recording")
    init.add_argument("--fallback", choices=("tts", "error"), default="error")
    init.add_argument("--voice")
    init.add_argument("--locale", default="en-US")
    capture = commands.add_parser(
        "import",
        help="copy an explicitly mapped local recording privately; preserve original bytes",
    )
    capture.add_argument("function_id")
    capture.add_argument("--sources", type=Path, required=True)
    capture.add_argument("--file", type=Path, required=True)
    capture.add_argument("--id", required=True)
    target = capture.add_mutually_exclusive_group(required=True)
    target.add_argument("--event")
    target.add_argument("--resource")
    capture.add_argument("--unit", type=int)
    capture.add_argument(
        "--start", type=float, help="explicit segment start in seconds after file preparation"
    )
    capture.add_argument(
        "--end", type=float, help="explicit segment end in seconds after file preparation"
    )
    capture.add_argument("--speaker", required=True)
    capture.add_argument("--session", default="unversioned-session")
    capture.add_argument("--version", default="1")
    capture.add_argument(
        "--consent",
        choices=("unknown", "self-recorded", "authorized-contributor", "synthetic-fixture"),
        default="unknown",
    )
    for name in ("inspect", "preprocess"):
        command = commands.add_parser(
            name, help="objective audio measurements; no transcript or perceptual approval"
        )
        command.add_argument("file", type=Path)
        if name == "preprocess":
            command.add_argument("--processing", type=Path)
            command.add_argument("--rate", type=int, default=44100)
            command.add_argument("--channels", type=int, choices=(1, 2), default=1)
            command.add_argument("--output", type=Path, required=True)


def session_document(function_id, locale="en-US"):
    from .complete_session import build_complete_session_plan

    plan = build_complete_session_plan(function_id, locale=locale)
    return resolve_document(plan["template_plan"], locale, strict=True)


def source_resolver(function_id, sources, *, locale="en-US", voice=None):
    """Share inherited function/template voice precedence with queued identity planning."""
    from .complete_session import _resolve_template
    from .session_overrides import resolve

    document = session_document(function_id, locale)
    template, binding = _resolve_template(function_id, None)
    options, _ = resolve(binding)
    return SourceResolver(
        document,
        sources,
        locale=locale,
        default_voice=voice or options.get("voice_profile"),
        fallback_voice=template.get("voice_profile"),
    )


def coverage(function_id, *, locale="en-US", sources=None):
    if sources:
        return source_resolver(function_id, sources, locale=locale).report
    doc = session_document(function_id, locale)
    return {
        "function_id": function_id,
        "locale": locale,
        "recordings_selected": False,
        "events": [
            {
                "event_id": event["id"],
                "narration_key": event.get("narration_key"),
                "text_sha256": text_fingerprint(event.get("text", "")),
                "text": event.get("text", ""),
                "source": "unselected" if event.get("text", "").strip() else "silence",
            }
            for event in iter_events(doc)
        ],
    }


def import_recording(
    function_id,
    sources,
    source,
    *,
    recording_id,
    speaker,
    event_id=None,
    resource=None,
    unit_index=None,
    session_id="unversioned-session",
    version="1",
    consent="unknown",
    segment=None,
):
    """Bind explicit semantic identity and exact text; existence never grants approval."""
    from .narration_pacing import plan_event_pacing
    from .recording_audio import inspect_recording

    path = Path(sources).resolve()
    data = load_yaml_file(path)
    # Validate the contract without requiring incomplete recorded-only coverage.
    from .validators import _load_schema, validate_against_schema

    errors = validate_against_schema(data, _load_schema("narration-sources.schema.json"))
    if errors:
        raise OCFError("invalid narration sources: " + " | ".join(errors))
    if recording_id in data.get("recordings", {}):
        raise OCFError("recording ID already exists; import a new version/ID")
    locale = data["locale"]
    doc = session_document(function_id, locale)
    matches = [
        event
        for event in iter_events(doc)
        if event.get("text", "").strip()
        and (event["id"] == event_id if event_id else event.get("narration_key") == resource)
    ]
    if not matches:
        raise OCFError("unknown spoken narration event/resource")
    texts = {event["text"] for event in matches}
    if len(texts) != 1:
        raise OCFError("resource has differing resolved text; select an explicit event")
    text = next(iter(texts))
    if unit_index is not None:
        pacing = plan_event_pacing(doc, matches[0])
        if not pacing or not 1 <= unit_index <= len(pacing["units"]):
            raise OCFError("unknown semantic unit index for selected narration event")
        text = pacing["units"][unit_index - 1]["text"]
    source = Path(source).resolve()
    measured = inspect_recording(source)
    checksum = sha256_of_file(source)
    directory = path.parent / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (checksum + source.suffix.lower())
    if target.exists() and sha256_of_file(target) != checksum:
        raise OCFError("existing recording asset checksum mismatch")
    if not target.exists():
        with target.open("xb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
    selector = (
        {"event_id": event_id}
        if event_id
        else {"narration_key": resource, "function_id": function_id}
    )
    if unit_index is not None:
        selector["unit_index"] = unit_index
    entry = {
        "file": target.relative_to(path.parent).as_posix(),
        "sha256": checksum,
        "text_sha256": text_fingerprint(text),
        "locale": locale,
        "speaker": speaker,
        "session_id": session_id,
        "version": version,
        "target": selector,
        "approval": "pending",
        "rights": {"consent": consent, "license": "unknown", "redistribution_permission": False},
    }
    data.setdefault("recordings", {})[recording_id] = entry
    if segment is not None:
        if not 0 <= segment["start_s"] < segment["end_s"] <= measured["original"]["duration_s"]:
            raise OCFError("segment markers are reversed or beyond source audio")
        entry["segment"] = segment
    errors = validate_against_schema(data, _load_schema("narration-sources.schema.json"))
    if errors:
        raise OCFError("invalid recording metadata: " + " | ".join(errors))
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return {
        "recording_id": recording_id,
        "recording": entry,
        "measurements": measured,
        "original_preserved": True,
        "transcript_verified": False,
    }


def dispatch(args):
    if args.narration_kind in ("sources", "preview", "validate"):
        if args.narration_kind != "sources" and not args.sources:
            raise OCFError("preview/validate requires --sources")
        return coverage(args.function_id, locale=args.locale, sources=args.sources)
    if args.narration_kind == "init":
        plan = coverage(args.function_id, locale=args.locale)
        manifest = {
            "schema_version": "2.0",
            "id": args.function_id.lower() + "-narration",
            "locale": args.locale,
            "mode": args.mode,
            "fallback": args.fallback,
            "recordings": {},
        }
        if args.voice:
            manifest["default_voice"] = args.voice
        write_text_atomic(args.output, json.dumps(manifest, indent=2) + "\n", overwrite=False)
        return {
            "path": str(args.output),
            "manifest": manifest,
            "spoken_events": sum(row["source"] == "unselected" for row in plan["events"]),
            "recordings_created": False,
        }
    if args.narration_kind == "import":
        if (args.start is None) != (args.end is None):
            raise OCFError("segment import requires both --start and --end")
        return import_recording(
            args.function_id,
            args.sources,
            args.file,
            recording_id=args.id,
            speaker=args.speaker,
            event_id=args.event,
            resource=args.resource,
            unit_index=args.unit,
            session_id=args.session,
            version=args.version,
            consent=args.consent,
            segment={"start_s": args.start, "end_s": args.end} if args.start is not None else None,
        )
    from .recording_audio import inspect_recording, process_recording

    if args.narration_kind == "inspect":
        return inspect_recording(args.file)
    if (
        args.output.suffix.lower() != ".wav"
        or args.output.exists()
        or args.output.with_suffix(".processing.json").exists()
    ):
        raise OCFError("choose a new .wav output and sidecar path")
    audio, report = process_recording(
        args.file,
        sample_rate=args.rate,
        channels=args.channels,
        processing=load_yaml_file(args.processing) if args.processing else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(audio)
    write_text_atomic(
        args.output.with_suffix(".processing.json"),
        json.dumps(report, indent=2) + "\n",
        overwrite=False,
    )
    return {"path": str(args.output), "report": report}
