"""Command-line interface for OCF.

Entry points:
    ./scripts/ocf
    python3 scripts/ocf.py
    ocf                          (if installed via pip)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import audio as audio_mod
from . import farfield as farfield_mod
from . import voice as voice_mod
from .indexes import (
    count_proposals,
    load_all_functions,
    load_audio_manifests,
    load_background_manifests,
)
from .paths import REPO_ROOT, SCHEMAS_DIR
from .prompts import (
    run_audio_wizard,
    run_background_wizard,
    run_edit_function,
    run_function_wizard,
    run_import_source,
    run_proposal_wizard,
    run_test_report_wizard,
)
from .utils import OCFError
from .validators import (
    print_result,
    validate_all,
    validate_function_file,
)

HELP_TEXT = """\
Open Consciousness Functions (OCF) — command-line tools.

Usage:
  ocf new function            Create a new function record (wizard)
  ocf new proposal            Create a new proposal (wizard)
  ocf new audio               Register an audio implementation (wizard)
  ocf new background          Register a background preset (wizard)
  ocf new test-report         Create a testing report (wizard)
  ocf import source           Fingerprint (and optionally copy) a source file
  ocf edit function <id|slug> Open a function record in $EDITOR
  ocf validate [--all]        Validate current / all records + rule checks
  ocf build-index [--check]   Regenerate generated indexes (or verify freshness)
  ocf review commands         Lint command design and print the review report
  ocf audio check-engine      Detect the optional background engines (Farfield, SBaGenX, ffmpeg)
  ocf audio list-background   List background presets
  ocf audio describe-background <preset> [--engine farfield|sbagenx|reference-master]
  ocf audio render-background <preset> [--output FILE] [--engine farfield|sbagenx|reference-master]
  ocf voice list-backends     List detected TTS backends (espeak-ng/espeak/piper)
  ocf voice doctor            Backend + voice-profile health check
  ocf voice list              List voice profiles (audio/voices/profiles/)
  ocf voice render SCRIPT [--voice NAME] [--output WAV] [--fit] [--flow] [--even-counts] [--force]
  ocf audio render-speech SCRIPT [--voice NAME] [--output WAV] [--force]
  ocf audio mix --speech A.wav [--background B.wav] --output MIX.wav [--background-gain 0.25] [--force]
  ocf audio build <AUDIO_ID> [--format wav|flac|mp3]... [--tag KEY=VALUE]... [--voice NAME] [--output DIR] [--fit] [--flow] [--even-counts] [--background-gain 0.25] [--force]
  ocf audio inspect FILE      Show audio file metadata + sha256
  ocf session list-templates  List session-composition templates (audio/templates/sessions/)
  ocf session compose [--template ID|FILE] [--opener FILE] [--focus11 FILE] [--sleep20 FILE] [--closer FILE] [--slot NAME=PATH]... [--title TITLE] [--id SLUG] [--duration SECONDS] [--output YAML] [--force]
                             Compose a learn-session script (opener + focus-11 function + sleep-20 reinforcement + closer) into canonical timed YAML
  ocf transcript import FILE [--format auto|lrc|srt|vtt|txt|md] [--output] [--title] [--force]
  ocf transcript analyze FILE [--interactive]
  ocf transcript segment FILE [--apply] [--output]
  ocf transcript review FILE [--state-profile NAME] [--write] [--output]
  ocf transcript export FILE --format srt|vtt|lrc [--output] [--force]
  ocf transcript extract-template FILE --timing-only [--output] [--force]
  ocf doctor                  Show environment health
  ocf help                    Show this help

Global flags:
  --quiet                     Suppress non-error output where supported
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocf", description=HELP_TEXT, add_help=False)
    parser.add_argument("--quiet", action="store_true", help="suppress informational output")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("help", help="show help")

    new = sub.add_parser("new", help="create a new record")
    new_sub = new.add_subparsers(dest="new_kind")
    new_sub.add_parser("function", help="new function record")
    new_sub.add_parser("proposal", help="new proposal")
    new_sub.add_parser("audio", help="new audio implementation manifest")
    new_sub.add_parser("background", help="new background preset manifest")
    new_sub.add_parser("test-report", help="new testing report")

    importer = sub.add_parser("import", help="import a source file")
    importer_sub = importer.add_subparsers(dest="import_kind")
    importer_sub.add_parser("source", help="fingerprint/copy a source file")

    edit = sub.add_parser("edit", help="edit a record")
    edit_sub = edit.add_subparsers(dest="edit_kind")
    edit_fn = edit_sub.add_parser("function", help="edit a function record")
    edit_fn.add_argument("query", nargs="?", help="function slug or id")

    validate = sub.add_parser("validate", help="validate records")
    validate.add_argument("--all", action="store_true", help="validate everything")
    validate.add_argument("path", nargs="?", help="validate a specific function file")

    build = sub.add_parser("build-index", help="regenerate derived indexes")
    build.add_argument("--check", action="store_true", help="fail if indexes are stale")

    review = sub.add_parser("review", help="command review tooling")
    review_sub = review.add_subparsers(dest="review_kind")
    review_sub.add_parser("commands", help="lint commands and print the review report")

    audio = sub.add_parser("audio", help="audio tooling")
    audio_sub = audio.add_subparsers(dest="audio_kind")
    audio_sub.add_parser("check-engine", help="check optional background synthesis engines (Farfield, SBaGenX)")
    audio_sub.add_parser("list-background", help="list background presets")
    describe = audio_sub.add_parser("describe-background", help="describe a background preset")
    describe.add_argument("preset", help="preset id or name")
    describe.add_argument("--engine", default="farfield", choices=["farfield", "sbagenx", "reference-master"],
                          help="engine to describe (default farfield)")
    render = audio_sub.add_parser("render-background", help="render a background preset")
    render.add_argument("preset", help="preset id or name")
    render.add_argument("--output", help="output file path")
    render.add_argument("--engine", default="farfield", choices=["farfield", "sbagenx", "reference-master"],
                        help="engine to render with (default farfield)")

    render_speech = audio_sub.add_parser("render-speech", help="render narration speech to WAV")
    render_speech.add_argument("file", help="OCF timed YAML document")
    render_speech.add_argument("--voice", help="voice profile id/slug or backend name")
    render_speech.add_argument("--output", help="output WAV path")
    render_speech.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    render_speech.add_argument("--force", action="store_true", help="overwrite an existing file")
    mix = audio_sub.add_parser("mix", help="mix narration with background audio")
    mix.add_argument("--speech", required=True, help="narration WAV")
    mix.add_argument("--background", help="optional background WAV")
    mix.add_argument("--output", required=True, help="mixed WAV path")
    mix.add_argument("--background-gain", type=float, default=0.25, help="background level (0-1)")
    mix.add_argument("--force", action="store_true", help="overwrite an existing file")
    build_cmd = audio_sub.add_parser("build", help="build a mastered audio implementation")
    build_cmd.add_argument("query", help="audio implementation id or manifest path")
    build_cmd.add_argument(
        "--format",
        action="append",
        choices=["wav", "flac", "mp3"],
        default=["wav", "flac", "mp3"],
        help="output format(s) (repeatable; default: all three)",
    )
    build_cmd.add_argument(
        "--tag",
        action="append",
        default=[],
        help="metadata tag override KEY=VALUE applied to FLAC/MP3 outputs (repeatable)",
    )
    build_cmd.add_argument("--voice", help="voice profile id/slug or backend name")
    build_cmd.add_argument("--output", help="output directory (default audio/rendered)")
    build_cmd.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    build_cmd.add_argument("--background-gain", type=float, default=0.25)
    build_cmd.add_argument("--fit", action="store_true", help="adaptive per-cue narration pacing (timing_mode fit-soft)")
    build_cmd.add_argument("--flow", action="store_true", help="flow-merge sentence fragments (timing_mode natural)")
    build_cmd.add_argument("--even-counts", action="store_true", help="re-time count cues onto even grids (timing_mode ...+even-counts)")
    build_cmd.add_argument("--force", action="store_true", help="overwrite master file")
    inspect_cmd = audio_sub.add_parser("inspect", help="show audio file metadata")
    inspect_cmd.add_argument("file", help="audio file")

    voice = sub.add_parser("voice", help="narration (TTS) tooling")
    voice_sub = voice.add_subparsers(dest="voice_kind")
    voice_sub.add_parser("list-backends", help="list detected TTS backends")
    voice_sub.add_parser("doctor", help="backend + profile health check")
    voice_sub.add_parser("list", help="list voice profiles")
    voice_render = voice_sub.add_parser("render", help="render narration speech to WAV")
    voice_render.add_argument("file", help="OCF timed YAML document")
    voice_render.add_argument("--voice", help="voice profile id/slug or backend name")
    voice_render.add_argument("--output", help="output WAV path")
    voice_render.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    voice_render.add_argument("--fit", action="store_true", help="adaptive per-cue pacing (trim TTS pads, fill short slots)")
    voice_render.add_argument("--flow", action="store_true", help="flow-merge sentence fragments into single utterances")
    voice_render.add_argument("--even-counts", action="store_true", help="re-time count cues onto even grids (no transcript rewrite)")
    voice_render.add_argument("--force", action="store_true", help="overwrite an existing file")

    transcript = sub.add_parser("transcript", help="timed-transcript tooling")
    ts = transcript.add_subparsers(dest="transcript_kind")
    imp = ts.add_parser("import", help="import a transcript into OCF timed YAML")
    imp.add_argument("file", help="LRC/SRT/VTT/TXT/MD transcript file")
    imp.add_argument(
        "--format",
        default="auto",
        choices=["auto", "lrc", "srt", "vtt", "txt", "md", "yaml"],
        help="input format (default: auto)",
    )
    imp.add_argument("--output", help="output YAML path")
    imp.add_argument("--title", help="document title (default: source metadata or filename)")
    imp.add_argument("--force", action="store_true", help="overwrite an existing output file")
    ana = ts.add_parser("analyze", help="structural analysis (all findings are suggestions)")
    ana.add_argument("file", help="OCF timed YAML document")
    ana.add_argument(
        "--interactive", action="store_true", help="step through suggested section boundaries"
    )
    seg = ts.add_parser("segment", help="assign section roles to the timeline")
    seg.add_argument("file", help="OCF timed YAML document")
    seg.add_argument(
        "--apply", action="store_true", help="apply all suggested boundaries without prompting"
    )
    seg.add_argument("--output", help="output YAML path (default: in place)")
    seg.add_argument("--force", action="store_true", help="overwrite an existing output file")
    rev = ts.add_parser("review", help="validate and summarize a timed transcript")
    rev.add_argument("file", help="OCF timed YAML document")
    rev.add_argument("--state-profile", help="set the document state_profile")
    rev.add_argument("--write", action="store_true", help="write reviewed changes back to file")
    rev.add_argument("--output", help="output YAML path (with --write)")
    rev.add_argument("--force", action="store_true", help="overwrite an existing output file")
    exp = ts.add_parser("export", help="export to SRT/VTT/LRC")
    exp.add_argument("file", help="OCF timed YAML document")
    exp.add_argument("--format", required=True, choices=["srt", "vtt", "lrc"], help="export format")
    exp.add_argument("--output", help="output file path (default: stdout)")
    exp.add_argument("--force", action="store_true", help="overwrite an existing output file")
    xt = ts.add_parser("extract-template", help="timing-only structural template")
    xt.add_argument("file", help="OCF timed YAML document")
    xt.add_argument(
        "--timing-only", action="store_true", required=True, help="omit all transcript text"
    )
    xt.add_argument("--output", help="output YAML path (default: stdout)")
    xt.add_argument("--force", action="store_true", help="overwrite an existing output file")

    session = sub.add_parser("session", help="session-composition templates (spec 46/55/58)")
    session_sub = session.add_subparsers(dest="session_kind")
    session_sub.add_parser("list-templates", help="list session templates in the library")
    compose_cmd = session_sub.add_parser(
        "compose",
        help="resolve a session template with contributor wording into canonical timed YAML",
    )
    compose_cmd.add_argument("--template", default="OCF-TPL-SESSION-LEARN-001",
                             help="template id or local template file path")
    compose_cmd.add_argument("--opener", help="text file with the opener wording (required only by templates that declare it)")
    compose_cmd.add_argument("--focus11", help="text file with the function material spoken while in the focus-11 state (required only by templates that declare it)")
    compose_cmd.add_argument("--sleep20", help="text file with the sleep-20 function reinforcement (required only by templates that declare it)")
    compose_cmd.add_argument("--closer", help="text file with the closer wording (required only by templates that declare it)")
    compose_cmd.add_argument("--slot", action="append", default=[],
                             help="fill a template slot NAME=PATH (repeatable; only slots the template declares are accepted)")
    compose_cmd.add_argument("--title", help="document title (default: template name)")
    compose_cmd.add_argument("--id", help="document/slug id (default: none)")
    compose_cmd.add_argument("--duration", type=float, help="total track length in seconds")
    compose_cmd.add_argument("--line-seconds", type=float, help="pace untimed slot lines every N seconds")
    compose_cmd.add_argument("--output", help="output YAML path (default audio/scripts/<id>.yaml)")
    compose_cmd.add_argument("--force", action="store_true", help="overwrite an existing output file")

    sub.add_parser("doctor", help="environment health check")
    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    """Route `validate`."""
    if args.path:
        result = validate_function_file(Path(args.path))
        return print_result(result)
    if args.all:
        result = validate_all()
    else:
        result = validate_all()
    return print_result(result)


def cmd_build_index(args: argparse.Namespace) -> int:
    """Route `build-index`."""
    from .generators import indexes_are_fresh, refresh_indexes

    if args.check:
        if indexes_are_fresh():
            print("Generated indexes are fresh.")
            return 0
        print("Generated indexes are STALE. Run: python3 scripts/ocf.py build-index")
        return 1
    refresh_indexes()
    print("Generated indexes updated.")
    return 0


def cmd_review_commands() -> int:
    """Route `review commands`."""
    from .generators import command_review_markdown
    from .paths import REPO_ROOT

    target = REPO_ROOT / "docs" / "COMMAND_REVIEW.md"
    from .utils import write_text_atomic

    write_text_atomic(target, command_review_markdown())
    print(f"Command review report written to {target.relative_to(REPO_ROOT)}")
    print("\nFor the full unified review, print the generated document above.")
    return 0


def cmd_doctor() -> int:
    """Environment health check."""
    checks: list[tuple[str, bool, str]] = []
    checks.append(("repository root", True, str(REPO_ROOT)))
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
    fits = sys.version_info >= (3, 11)
    checks.append(("python (need >=3.11)", fits, python))

    try:
        import yaml  # noqa: F401

        checks.append(("PyYAML", True, "available"))
    except ImportError:
        checks.append(("PyYAML", False, "missing — pip install PyYAML"))

    try:
        import jsonschema  # noqa: F401

        checks.append(("jsonschema", True, "available"))
    except ImportError:
        checks.append(("jsonschema", False, "missing — pip install jsonschema"))

    checks.append(("schemas present", SCHEMAS_DIR.is_dir(), str(SCHEMAS_DIR)))
    functions = load_all_functions()
    checks.append(("function records", functions is not None, f"{len(functions)} loaded"))
    checks.append(("proposals", True, f"{count_proposals()} files"))
    checks.append(("audio manifests", True, f"{len(load_audio_manifests())} files"))
    checks.append(("background manifests", True, f"{len(load_background_manifests())} files"))

    far_status = farfield_mod.check_farfield()
    checks.append(
        (
            "farfield engine",
            far_status.available,
            far_status.executable or "NOT installed (optional)",
        )
    )

    failed = 0
    for label, ok, detail in checks:
        mark = "[ok] " if ok else "[!!] "
        print(f"{mark}{label}: {detail}")
        if not ok:
            failed += 1
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed.")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(HELP_TEXT)
        return 0

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse exits on unknown subcommands or missing required arguments;
        # degrade gracefully to the help text instead.
        print(HELP_TEXT)
        return 0

    try:
        if args.command == "help" or args.command is None:
            print(HELP_TEXT)
            return 0
        if args.command == "new":
            if args.new_kind == "function":
                run_function_wizard()
            elif args.new_kind == "proposal":
                run_proposal_wizard()
            elif args.new_kind == "audio":
                run_audio_wizard()
            elif args.new_kind == "background":
                run_background_wizard()
            elif args.new_kind == "test-report":
                run_test_report_wizard()
            else:
                print(HELP_TEXT)
            return 0
        if args.command == "import" and args.import_kind == "source":
            run_import_source()
            return 0
        if args.command == "edit" and args.edit_kind == "function":
            run_edit_function(getattr(args, "query", None))
            return 0
        if args.command == "validate":
            return cmd_validate(args)
        if args.command == "build-index":
            return cmd_build_index(args)
        if args.command == "review" and args.review_kind == "commands":
            return cmd_review_commands()
        if args.command == "audio":
            if args.audio_kind == "check-engine":
                return audio_mod.check_engine()
            if args.audio_kind == "list-background":
                return audio_mod.list_background()
            if args.audio_kind == "describe-background":
                return audio_mod.describe_background(
                    args.preset, getattr(args, "engine", "farfield")
                )
            if args.audio_kind == "render-background":
                return audio_mod.render_background(
                    args.preset, getattr(args, "output", None), getattr(args, "engine", "farfield")
                )
            if args.audio_kind == "render-speech":
                from .audio_build import default_narration_output

                out = getattr(args, "output", None) or default_narration_output(args.file)
                return voice_mod.render_script(
                    args.file,
                    out,
                    backend=args.voice,
                    sample_rate=args.rate,
                    force=args.force,
                )
            if args.audio_kind == "mix":
                from .audio_build import mix as mix_tracks

                mix_tracks(
                    args.speech,
                    args.background,
                    args.output,
                    background_gain=args.background_gain,
                    overwrite=args.force,
                )
                return 0
            if args.audio_kind == "build":
                from .audio_build import build as run_build

                tag_overrides: dict[str, str] = {}
                for spec in getattr(args, "tag", []) or []:
                    if "=" not in spec:
                        raise OCFError(f"--tag expects KEY=VALUE, got {spec!r}")
                    key, value = spec.split("=", 1)
                    tag_overrides[key.strip()] = value.strip()
                run_build(
                    args.query,
                    out_root=getattr(args, "output", None),
                    formats=args.format,
                    tag_overrides=tag_overrides,
                    voice=args.voice,
                    background_gain=args.background_gain,
                    sample_rate=args.rate,
                    overwrite=args.force,
                    fit=bool(getattr(args, "fit", False)),
                    flow=bool(getattr(args, "flow", False)),
                    even_counts=bool(getattr(args, "even_counts", False)),
                )
                return 0
            if args.audio_kind == "inspect":
                from .audio_build import inspect as inspect_file
                from .utils import yaml_safe_dump

                print(yaml_safe_dump(inspect_file(args.file)).rstrip())
                return 0
            print(HELP_TEXT)
            return 0
        if args.command == "voice":
            if args.voice_kind == "list-backends":
                return voice_mod.list_backends_cmd()
            if args.voice_kind == "doctor":
                return voice_mod.voice_doctor()
            if args.voice_kind == "list":
                return voice_mod.list_profiles_cmd()
            if args.voice_kind == "render":
                from .audio_build import default_narration_output

                out = getattr(args, "output", None) or default_narration_output(args.file)
                return voice_mod.render_script(
                    args.file,
                    out,
                    backend=args.voice,
                    sample_rate=args.rate,
                    force=args.force,
                    fit=bool(getattr(args, "fit", False)),
                    flow=bool(getattr(args, "flow", False)),
                    even_counts=bool(getattr(args, "even_counts", False)),
                )
            print(HELP_TEXT)
            return 0
        if args.command == "transcript":
            from .transcript import run_transcript

            return run_transcript(args)
        if args.command == "session":
            from .session import run_compose, run_list_templates

            if args.session_kind == "list-templates":
                return run_list_templates()
            if args.session_kind == "compose":
                return run_compose(args)
            print(HELP_TEXT)
            return 0
        if args.command == "doctor":
            return cmd_doctor()
        print(HELP_TEXT)
        return 0
    except OCFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
