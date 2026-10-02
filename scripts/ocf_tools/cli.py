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
from typing import Any

from . import audio as audio_mod
from . import voice as voice_mod
from .indexes import load_all_functions
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
  ocf locale list              List locale packs with provenance and coverage
  ocf locale coverage [--locale TAG] [--domain ui|narration]
  ocf locale validate [--locale TAG] [--file DOC] [--json]
  ocf locale resolve (--file DOC | --session TEMPLATE) --locale TAG [--no-strict] [--output YAML]
  ocf locale pseudo [--from TAG] [--locale TAG] [--output DIR]
  ocf doctor                  Show environment health
  ocf capabilities --json    Discover live command paths and schemas
  ocf functions list --json  Discover canonical function records
  ocf functions describe ID --json
  ocf corpus inventory [--root DIR] [--format json|md] [--output FILE]
  ocf help                    Show this help

Global flags:
  --quiet                     Suppress non-error output where supported
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocf", description=HELP_TEXT, add_help=False)
    parser.add_argument("--quiet", action="store_true", help="suppress informational output")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("help", help="show help")
    capabilities = sub.add_parser("capabilities", help="machine-readable live CLI discovery")
    capabilities.add_argument("--json", action="store_true")
    author_plan = sub.add_parser(
        "plan", help="validate a structured authoring request without rendering"
    )
    author_plan.add_argument("file")
    author_plan.add_argument("--json", action="store_true")
    functions = sub.add_parser("functions", help="canonical function metadata discovery")
    function_sub = functions.add_subparsers(dest="function_kind", required=True)
    function_list = function_sub.add_parser("list", help="list all function records")
    function_list.add_argument("--json", action="store_true")
    function_list.add_argument(
        "--rich", action="store_true", help="include separate content/evidence/runtime capabilities"
    )
    function_describe = function_sub.add_parser(
        "describe", help="describe a canonical function ID or slug"
    )
    function_describe.add_argument("id")
    function_describe.add_argument("--json", action="store_true")
    function_describe.add_argument("--rich", action="store_true")

    corpus = sub.add_parser(
        "corpus", help="citation-only research inventory; no source wording copied"
    )
    corpus_sub = corpus.add_subparsers(dest="corpus_kind")
    inventory_cmd = corpus_sub.add_parser(
        "inventory", help="fingerprint all corpus files and map all legacy targets"
    )
    inventory_cmd.add_argument("--root", default=str(REPO_ROOT / "references/HumanPlusTranscripts"))
    inventory_cmd.add_argument("--format", choices=["json", "md"], default="json")
    inventory_cmd.add_argument("--output")

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
    audio_sub.add_parser(
        "check-engine", help="check optional background synthesis engines (Farfield, SBaGenX)"
    )
    audio_sub.add_parser("list-background", help="list background presets")
    describe = audio_sub.add_parser("describe-background", help="describe a background preset")
    describe.add_argument("preset", help="preset id or name")
    describe.add_argument(
        "--engine",
        default="farfield",
        choices=["farfield", "sbagenx", "reference-master"],
        help="engine to describe (default farfield)",
    )
    render = audio_sub.add_parser("render-background", help="render a background preset")
    render.add_argument("preset", help="preset id or name")
    render.add_argument("--output", help="output file path")
    render.add_argument(
        "--engine",
        default="farfield",
        choices=["farfield", "sbagenx", "reference-master"],
        help="engine to render with (default farfield)",
    )

    render_speech = audio_sub.add_parser("render-speech", help="render narration speech to WAV")
    render_speech.add_argument("file", help="OCF timed YAML document")
    render_speech.add_argument("--voice", help="voice profile id/slug or backend name")
    render_speech.add_argument(
        "--recordings", help="event-mapped prerecorded narration package (instead of TTS)"
    )
    render_speech.add_argument(
        "--locale", help="target locale (BCP-47); resolves narration keys and retargets the voice"
    )
    render_speech.add_argument(
        "--allow-fallback",
        action="store_true",
        help="permit fallback across the locale chain instead of failing on missing spoken narration",
    )
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
    build_cmd.add_argument(
        "--recordings", help="event-mapped prerecorded narration package (instead of TTS)"
    )
    build_cmd.add_argument("--locale", help="target locale (BCP-47) for narration rendering")
    build_cmd.add_argument(
        "--allow-fallback",
        action="store_true",
        help="permit fallback across the locale chain instead of failing on missing spoken narration",
    )
    build_cmd.add_argument("--output", help="output directory (default audio/rendered)")
    build_cmd.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    build_cmd.add_argument("--background-gain", type=float, default=0.25)
    build_cmd.add_argument(
        "--dsp-profile",
        help="semantic DSP state-selection profile (explicitly overrides a static bed)",
    )
    build_cmd.add_argument(
        "--fit",
        action="store_true",
        help="adaptive per-cue narration pacing (timing_mode fit-soft)",
    )
    build_cmd.add_argument(
        "--flow", action="store_true", help="flow-merge sentence fragments (timing_mode natural)"
    )
    build_cmd.add_argument(
        "--even-counts",
        action="store_true",
        help="re-time count cues onto even grids (timing_mode ...+even-counts)",
    )
    build_cmd.add_argument("--force", action="store_true", help="overwrite master file")
    inspect_cmd = audio_sub.add_parser("inspect", help="show audio file metadata")
    inspect_cmd.add_argument("file", help="audio file")
    state_render = audio_sub.add_parser(
        "render-state-program", help="render configured DSP from a measured semantic ledger"
    )
    state_render.add_argument("file", help="semantic timed script")
    state_render.add_argument(
        "--render-manifest", required=True, help="measured event timing and duration"
    )
    state_render.add_argument("--dsp-profile", required=True)
    state_render.add_argument("--output", required=True)
    state_render.add_argument("--force", action="store_true")

    voice = sub.add_parser("voice", help="narration (TTS) tooling")
    voice_sub = voice.add_subparsers(dest="voice_kind")
    voice_packs = voice_sub.add_parser(
        "packs", help="list declarative community voice metadata; no downloads"
    )
    voice_packs.add_argument("--json", action="store_true")
    recording_import = voice_sub.add_parser(
        "import-recordings",
        help="create a measured package from an explicitly mapped recordings directory",
    )
    recording_import.add_argument("file", help="semantic session document")
    recording_import.add_argument("--directory", required=True)
    recording_import.add_argument(
        "--mapping", required=True, help="JSON occurrence/event ID to filename map"
    )
    recording_import.add_argument("--locale", required=True)
    recording_import.add_argument("--author", required=True)
    recording_import.add_argument("--license", required=True)
    recording_import.add_argument("--speaker")
    recording_import.add_argument("--output", required=True)
    voice_sub.add_parser("list-backends", help="list detected TTS backends")
    voice_sub.add_parser("doctor", help="backend + profile health check")
    voice_sub.add_parser("list", help="list voice profiles")
    voice_render = voice_sub.add_parser("render", help="render narration speech to WAV")
    voice_render.add_argument("file", help="OCF timed YAML document")
    voice_render.add_argument("--voice", help="voice profile id/slug or backend name")
    voice_render.add_argument(
        "--recordings", help="event-mapped prerecorded narration package (instead of TTS)"
    )
    voice_render.add_argument(
        "--locale", help="target locale (BCP-47); resolves narration keys and retargets the voice"
    )
    voice_render.add_argument(
        "--allow-fallback",
        action="store_true",
        help="permit fallback across the locale chain instead of failing on missing spoken narration",
    )
    voice_render.add_argument("--output", help="output WAV path")
    voice_render.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    voice_render.add_argument(
        "--fit",
        action="store_true",
        help="adaptive per-cue pacing (trim TTS pads, fill short slots)",
    )
    voice_render.add_argument(
        "--flow", action="store_true", help="flow-merge sentence fragments into single utterances"
    )
    voice_render.add_argument(
        "--even-counts",
        action="store_true",
        help="re-time count cues onto even grids (no transcript rewrite)",
    )
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
    exp.add_argument("--locale", help="resolve narration keys into this locale before exporting")
    exp.add_argument(
        "--allow-fallback",
        action="store_true",
        help="permit fallback across the locale chain instead of failing on missing spoken narration",
    )
    exp.add_argument(
        "--render-manifest",
        help="use the measured speech timings from a render manifest (OCF-RENDER-*.yaml) for cue ends",
    )
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
    compose_cmd.add_argument(
        "--template",
        default="OCF-TPL-SESSION-LEARN-001",
        help="template id or local template file path",
    )
    compose_cmd.add_argument(
        "--opener",
        help="text file with the opener wording (required only by templates that declare it)",
    )
    compose_cmd.add_argument(
        "--focus11",
        help="text file with the function material spoken while in the focus-11 state (required only by templates that declare it)",
    )
    compose_cmd.add_argument(
        "--sleep20",
        help="text file with the sleep-20 function reinforcement (required only by templates that declare it)",
    )
    compose_cmd.add_argument(
        "--closer",
        help="text file with the closer wording (required only by templates that declare it)",
    )
    compose_cmd.add_argument(
        "--slot",
        action="append",
        default=[],
        help="fill a template slot NAME=PATH (repeatable; only slots the template declares are accepted)",
    )
    compose_cmd.add_argument("--title", help="document title (default: template name)")
    compose_cmd.add_argument("--id", help="document/slug id (default: none)")
    compose_cmd.add_argument("--duration", type=float, help="total track length in seconds")
    compose_cmd.add_argument(
        "--line-seconds", type=float, help="pace untimed slot lines every N seconds"
    )
    compose_cmd.add_argument(
        "--locale", help="compose directly in this locale (BCP-47), resolving narration keys"
    )
    compose_cmd.add_argument(
        "--enable-stage",
        action="append",
        help="enable an optional semantic stage feature (repeatable)",
    )
    compose_cmd.add_argument(
        "--function", help="function identity owning activation-command narration"
    )
    compose_cmd.add_argument(
        "--allow-fallback",
        action="store_true",
        help="permit fallback across the locale chain instead of failing on missing spoken narration",
    )
    compose_cmd.add_argument("--output", help="output YAML path (default audio/scripts/<id>.yaml)")
    compose_cmd.add_argument(
        "--force", action="store_true", help="overwrite an existing output file"
    )

    locale = sub.add_parser("locale", help="locale packs and localized narration")
    locale_sub = locale.add_subparsers(dest="locale_kind")
    locale_sub.add_parser("list", help="list locale packs, provenance, and coverage")
    cov = locale_sub.add_parser(
        "coverage", help="report a locale's key coverage against the canonical pack"
    )
    cov.add_argument("--locale", help="locale to report (default: every installed pack)")
    cov.add_argument("--domain", choices=["ui", "narration"], help="restrict to one domain")
    loc_validate = locale_sub.add_parser("validate", help="validate locale packs")
    loc_validate.add_argument("--locale", help="validate only this pack")
    loc_validate.add_argument(
        "--file", help="also resolve this timed document strictly (pre-render check)"
    )
    loc_validate.add_argument("--json", action="store_true", help="emit issues as JSON")
    loc_resolve = locale_sub.add_parser(
        "resolve", help="resolve a document's narration keys into one locale"
    )
    loc_resolve.add_argument("--file", help="OCF timed YAML document to resolve")
    loc_resolve.add_argument("--session", help="session template id/path to compose, then resolve")
    loc_resolve.add_argument("--locale", required=True, help="target locale (BCP-47)")
    loc_resolve.add_argument(
        "--no-strict",
        action="store_true",
        help="fall back through the locale chain instead of failing on missing spoken narration",
    )
    loc_resolve.add_argument("--output", help="output YAML path (default stdout)")
    loc_resolve.add_argument(
        "--force", action="store_true", help="overwrite an existing output file"
    )
    pseudo = locale_sub.add_parser("pseudo", help="derive a pseudo-locale pack from another pack")
    pseudo.add_argument("--from", dest="source_locale", help="source locale (default: canonical)")
    pseudo.add_argument("--locale", help="pseudo-locale tag (default: en-XA)")
    pseudo.add_argument("--output", help="write the pack here (default: print a sample)")

    doctor = sub.add_parser("doctor", help="core/workflow health; optional tools do not fail core")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument(
        "--workflow",
        choices=["core", "encode", "farfield", "sbagenx", "piper", "container"],
        default="core",
    )
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


def _locale_catalog() -> Any:
    from .locale import LocaleCatalog

    return LocaleCatalog()


def _locale_ui(catalog: Any, key: str, target: str | None = None, /, **variables: Any) -> str:
    """Format an operator-facing string from the pack, falling back to English.

    Only the variables the resource declares are passed through, so a caller can
    hand over every value it has without tripping the variable contract.
    """
    from .locale import LocalizationError

    lookup = target or catalog.canonical_locale
    try:
        entry, _resolution = catalog.resource(key, lookup)
        supplied = {name: value for name, value in variables.items() if name in entry.variables}
        return entry.render(supplied, plural_rules=catalog.plural_rules_for(lookup))
    except LocalizationError:
        return ", ".join(f"{name}={value}" for name, value in variables.items())


def cmd_locale_list() -> int:
    """Route `locale list`."""
    catalog = _locale_catalog()
    print(f"{_locale_ui(catalog, 'locale.list.header')} ({catalog.root})")
    for locale in catalog.locales():
        pack = catalog.require(locale)
        coverage = catalog.coverage(locale)
        print(f"  {pack.describe()}  {coverage['percent']}% of canonical keys")
        translation = pack.translation
        if translation:
            print(
                f"      source {translation.get('source_locale')}@"
                f"{translation.get('source_semantic_version')}  "
                f"translator {translation.get('translator')}  "
                f"direction {pack.direction}"
            )
    for problem in catalog.problems:
        print(f"  [ERROR] {problem}")
    return 1 if catalog.problems else 0


def cmd_locale_coverage(args: argparse.Namespace) -> int:
    """Route `locale coverage`."""
    catalog = _locale_catalog()
    locales = [args.locale] if args.locale else catalog.locales()
    for locale in locales:
        domain = getattr(args, "domain", None)
        stats = catalog.coverage(locale, domain=domain)
        key = "locale.coverage.narration" if domain == "narration" else "locale.coverage.line"
        print(
            _locale_ui(
                catalog,
                key,
                locale,
                locale=locale,
                covered=stats["covered"],
                total=stats["total"],
                percent=stats["percent"],
            )
        )
        for missing in catalog.missing_keys(locale, domain=domain):
            print(f"    missing {missing}")
    return 0


def cmd_locale_validate(args: argparse.Namespace) -> int:
    """Route `locale validate`."""
    import json as json_module

    from .indexes import load_yaml_file
    from .locale import LocalizationError, resolve_document
    from .validators import (
        ValidationResult,
        validate_locale_packs,
        validate_narration_hygiene,
        validate_narration_usage,
    )

    catalog = _locale_catalog()
    full = validate_locale_packs(catalog)
    result = full
    if getattr(args, "locale", None):
        wanted = args.locale
        result = ValidationResult()
        try:
            serving = catalog.spoken_chain(wanted)
        except LocalizationError as exc:
            result.add("error", "locale-unavailable", str(exc), wanted)
        else:
            paths = [str(catalog.require(tag).path) for tag in serving]
            for issue in full.issues:
                if issue.code == "locale-count" or any(
                    (issue.target or "").startswith(path) for path in paths
                ):
                    result.add(issue.severity, issue.code, issue.message, issue.target)
    if getattr(args, "file", None):
        path = Path(args.file)
        document = load_yaml_file(path)
        result.extend(validate_narration_usage(document, path, catalog))
        try:
            localized = resolve_document(
                document, getattr(args, "locale", None), catalog=catalog, strict=True
            )
            result.extend(validate_narration_hygiene(localized, path, catalog))
        except LocalizationError as exc:
            result.add("error", "narration-strict-missing", str(exc), str(path))
    if getattr(args, "json", False):
        print(
            json_module.dumps(
                {
                    "issues": [
                        {
                            "severity": issue.severity,
                            "code": issue.code,
                            "message": issue.message,
                            "target": issue.target,
                        }
                        for issue in result.issues
                    ]
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print_result(result)
    return 0 if result.ok else 1


def cmd_locale_resolve(args: argparse.Namespace) -> int:
    """Route `locale resolve`."""
    from .indexes import load_yaml_file
    from .locale import ResolutionReport, resolve_document
    from .session import compose, load_template
    from .utils import write_text_atomic, yaml_safe_dump

    catalog = _locale_catalog()
    if args.file and args.session:
        raise OCFError("pass either --file or --session, not both")
    if args.session:
        template = load_template(args.session)
        document = compose(
            template,
            {},
            title=str(template.get("name", template["id"])),
            document_id=f"{str(template['id']).lower()}-{args.locale.lower()}",
        )
        source = f"template {template['id']}"
    elif args.file:
        document = load_yaml_file(Path(args.file))
        source = str(args.file)
    else:
        raise OCFError("pass --file DOC or --session TEMPLATE")

    report = ResolutionReport()
    resolved = resolve_document(
        document,
        args.locale,
        catalog=catalog,
        strict=not args.no_strict,
        report=report,
    )
    body = yaml_safe_dump(resolved).rstrip() + "\n"
    if args.output:
        write_text_atomic(Path(args.output), body, overwrite=args.force)
        print(
            _locale_ui(
                catalog,
                "locale.resolve.wrote",
                args.locale,
                path=args.output,
                locale=args.locale,
                keys=len(report.keys),
            )
        )
        print(f"  from {source}")
    else:
        print(body.rstrip())
    return 0


def cmd_locale_pseudo(args: argparse.Namespace) -> int:
    """Route `locale pseudo`."""
    from .locale import PSEUDO_LOCALE, build_pseudo_pack
    from .paths import ensure_dir
    from .utils import yaml_safe_dump

    catalog = _locale_catalog()
    pack = build_pseudo_pack(catalog, args.source_locale, locale=args.locale or PSEUDO_LOCALE)
    source = catalog.require(args.source_locale or catalog.canonical_locale)
    if args.output:
        root = ensure_dir(Path(args.output))
        (root / "manifest.yaml").write_text(yaml_safe_dump(pack.manifest), encoding="utf-8")
        for filename in sorted({entry.file for entry in pack.entries.values() if entry.file}):
            by_domain: dict[str, dict[str, Any]] = {}
            for key, entry in sorted(pack.entries.items()):
                if entry.file != filename:
                    continue
                by_domain.setdefault(entry.domain, {})[key] = {
                    "text": entry.text,
                    "variables": sorted(entry.variables),
                    "status": entry.status,
                    "version": entry.version,
                    "pronunciation": dict(entry.pronunciation),
                    "requires_events": list(entry.requires_events),
                    "required_pronunciation": list(entry.required_pronunciation),
                }
            for domain, entries in sorted(by_domain.items()):
                (root / filename).write_text(
                    yaml_safe_dump(
                        {
                            "schema_version": "1.0",
                            "locale": pack.locale,
                            "domain": domain,
                            "entries": entries,
                        }
                    ),
                    encoding="utf-8",
                )
        print(
            _locale_ui(
                catalog,
                "locale.pseudo.built",
                pack.locale,
                locale=pack.locale,
                source=source.locale,
                version=source.semantic_version,
                count=len(pack.entries),
            )
        )
        return 0
    for key in pack.keys("narration")[:8]:
        print(f"{key}\n  {pack.entries[key].text}")
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


def cmd_doctor(args=None) -> int:
    import json

    from .diagnostics import diagnose

    result = diagnose(getattr(args, "workflow", "core"))
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    else:
        print(f"OCF core/workflow health: {result['workflow']}")
        for row in result["checks"]:
            print(f"[{row['status']}] {row['id']} ({row['requirement']}): {row['detail']}")
    return 0 if result["ok"] else 1


def capability_manifest(parser: argparse.ArgumentParser) -> dict:
    """Derive discovery from registered parsers, never advertise planned commands."""
    commands = []

    def walk(node: argparse.ArgumentParser, prefix: list[str]) -> None:
        subparsers = [
            action for action in node._actions if isinstance(action, argparse._SubParsersAction)
        ]
        if not subparsers:
            commands.append(
                {"path": prefix, "description": node.description or "Use --help for arguments"}
            )
        for action in subparsers:
            for name, child in action.choices.items():
                walk(child, [*prefix, name])

    walk(parser, [])
    return {
        "schema_version": "1.0",
        "commands": commands,
        "schemas": sorted(path.name for path in SCHEMAS_DIR.glob("*.schema.json")),
        "boundaries": [
            "Agent reasons; OCF validates and executes",
            "English narration does not define semantic identity",
            "Source derivatives and reconstructions remain citation-only research",
            "Preparation CLI and auditory cue playback remain unshipped",
        ],
    }


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
    except SystemExit as exc:
        # argparse exits on unknown subcommands or missing required arguments;
        # degrade gracefully to the help text instead.
        print(HELP_TEXT)
        return int(exc.code or 0)

    try:
        if args.command == "help" or args.command is None:
            print(HELP_TEXT)
            return 0
        if args.command == "plan":
            import json

            from .indexes import load_yaml_file
            from .planning import plan

            try:
                result = plan(load_yaml_file(Path(args.file)), Path(args.file).resolve().parent)
            except OCFError as exc:
                if not args.json:
                    raise
                print(json.dumps({"schema_version": "1.0", "valid": False, "errors": [str(exc)]}))
                return 1
            print(
                json.dumps(result, indent=2)
                if args.json
                else f"Valid dry-run plan: {result['template_id']} / {result['locale']} / {result['content_status']}"
            )
            return 0
        if args.command == "capabilities":
            import json

            data = capability_manifest(parser)
            print(
                json.dumps(data, indent=2)
                if args.json
                else "\n".join("ocf " + " ".join(row["path"]) for row in data["commands"])
            )
            return 0
        if args.command == "functions":
            import json

            from .content import discover
            from .indexes import load_function_by_slug_or_id

            if args.function_kind == "list":
                data = [
                    discover(record) if args.rich else record.data
                    for record in load_all_functions()
                ]
            else:
                record = load_function_by_slug_or_id(args.id)
                if record is None:
                    raise OCFError(f"unknown function {args.id}; use ocf functions list")
                data = discover(record) if args.rich else record.data
            if args.json:
                print(
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "functions": data if isinstance(data, list) else [data],
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                records = data if isinstance(data, list) else [data]
                for record in records:
                    if args.rich:
                        print(
                            f"{record['function_id']}: {record['title']} — {record['activation']['primary']} — {record['extraction_status']} / review {record['human_review']}"
                        )
                    else:
                        print(
                            f"{record['id']}: {record['canonical']['name']} — {record['canonical']['command']['primary']} — {record['purpose']['summary']}"
                        )
            return 0
        if args.command == "corpus" and args.corpus_kind == "inventory":
            import json

            from .corpus import inventory, markdown
            from .utils import write_text_atomic
            from .validators import _load_schema, validate_against_schema

            root = Path(args.root).expanduser().resolve()
            data = inventory(root)
            errors = validate_against_schema(data, _load_schema("corpus-inventory.schema.json"))
            if errors:
                raise OCFError("corpus inventory: " + " | ".join(errors))
            text = (
                markdown(data)
                if args.format == "md"
                else json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            )
            if args.output:
                output = Path(args.output).expanduser().resolve()
                if output.is_relative_to(root):
                    raise OCFError(
                        "derived inventory must be outside the reference corpus; originals are read-only"
                    )
                write_text_atomic(output, text)
            else:
                print(text, end="")
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
                    locale=getattr(args, "locale", None),
                    strict=not getattr(args, "allow_fallback", False),
                    recordings=getattr(args, "recordings", None),
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
            if args.audio_kind == "render-state-program":
                from .semantic_dsp import run_render_program

                return run_render_program(args)
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
                    dsp_profile=getattr(args, "dsp_profile", None),
                    recordings=getattr(args, "recordings", None),
                    locale=getattr(args, "locale", None),
                    strict=not getattr(args, "allow_fallback", False),
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
            if args.voice_kind == "packs":
                import json

                from .voice_registry import load_registry

                entries = load_registry()
                print(
                    json.dumps({"schema_version": "1.0", "voices": entries}, indent=2)
                    if args.json
                    else "\n".join(
                        f"{entry['id']}: {entry['display_name']} / {entry['install_status']}"
                        for entry in entries
                    )
                    or "No community voice packs registered"
                )
                return 0
            if args.voice_kind == "import-recordings":
                import json

                from .recordings import import_directory, unique_mapping
                from .transcript import load_timed_doc

                mapping = json.loads(
                    Path(args.mapping).read_text(encoding="utf-8"), object_pairs_hook=unique_mapping
                )
                result = import_directory(
                    load_timed_doc(Path(args.file)),
                    Path(args.directory),
                    mapping,
                    Path(args.output),
                    locale=args.locale,
                    author=args.author,
                    license=args.license,
                    speaker=args.speaker,
                )
                print(
                    f"Imported {len(result['recordings'])} measured recordings; originals preserved -> {args.output}"
                )
                return 0
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
                    locale=getattr(args, "locale", None),
                    strict=not getattr(args, "allow_fallback", False),
                    recordings=getattr(args, "recordings", None),
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
        if args.command == "locale":
            if args.locale_kind == "list" or args.locale_kind is None:
                return cmd_locale_list()
            if args.locale_kind == "coverage":
                return cmd_locale_coverage(args)
            if args.locale_kind == "validate":
                return cmd_locale_validate(args)
            if args.locale_kind == "resolve":
                return cmd_locale_resolve(args)
            if args.locale_kind == "pseudo":
                return cmd_locale_pseudo(args)
            print(HELP_TEXT)
            return 0
        if args.command == "doctor":
            return cmd_doctor(args)
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
