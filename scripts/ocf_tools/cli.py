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
from .utils import OCFError, read_json_object
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
  ocf new session-plan        Generate a bound complete-session source plan (wizard)
  ocf new voice               Create a private reusable voice profile (wizard)
  ocf artwork --help          Original candidate brand, themes, gallery and covers
  ocf voice audition VOICE... Compare original short passages across selected profiles
  ocf voice training-plan     Report verified capabilities and unsupported training blockers
  ocf audio review-sessions FUNCTION_ID... [--voice PROFILE]
  ocf dev OPERATION --arguments JSON  Compact agent APIs and persistent jobs
  ocf audio eligibility [FUNCTION_ID|--all] --locale en-US
  ocf audio plan [FUNCTION_ID|--all] [--locale TAG] [--dry-run|--check]
  ocf audio render-many [FUNCTION_ID ...|--all] --voice PROFILE [--dry-run|--resume|--force]
  ocf audio defaults          Verify immutable shared configuration hashes
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
  ocf audio render FUNCTION_ID [--mode session|narration-only] [--locale TAG] [--voice PROFILE] [--pacing normal|relaxed|sleep] [--template ID] [--output DIR] [--dry-run]
  ocf audio mix --speech A.wav [--background B.wav] --output MIX.wav [--background-gain 0.25] [--force]
  ocf audio build <AUDIO_ID> [--format wav|flac|mp3]... [--tag KEY=VALUE]... [--voice NAME] [--output DIR] [--voice-gain 1.0] [--background-gain 0.25] [--fit] [--flow] [--even-counts] [--force]
  ocf audio release <AUDIO_ID|FUNCTION_ID> --artwork IMAGE [--locale TAG] [--format mp3|flac]... [--voice NAME] [--output DIR] [--version VERSION] [--tag KEY=VALUE]... [--dry-run] [--force]
  ocf audio inspect FILE      Show audio file metadata + sha256
  ocf session list-templates  List session-composition templates (audio/templates/sessions/)
  ocf session compose [--template ID|FILE] [--pacing-profile ID|FILE]
                      [--opener FILE] [--focus11 FILE] [--sleep20 FILE] [--closer FILE]
                      [--slot NAME=PATH]... [--function FUNCTION_ID] [--locale LOCALE] [--title TITLE] [--id SLUG]
                      [--duration SECONDS] [--output YAML] [--force]
                             Compose a session template into canonical timed YAML
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
  ocf workspace clean [--older-than-hours N] [--dry-run]
  ocf functions list --json  Discover canonical function records
  ocf functions describe ID --json
  ocf functions lookup "HISTORICAL NAME" --locale en-US --json
  ocf commands list [--locale TAG] [--json]
  ocf commands describe ID [--locale TAG] [--json]
  ocf commands export [--locale TAG] [--format json|md] [--output FILE] [--force]
  ocf corpus inventory [--root DIR] [--format json|md] [--output FILE]
  ocf help                    Show this help

Global flags:
  --quiet                     Suppress non-error output where supported
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocf", description=HELP_TEXT, add_help=False)
    parser.add_argument("--quiet", action="store_true", help="suppress informational output")
    sub = parser.add_subparsers(dest="command")
    from .lsp_server import add_arguments as add_lsp_arguments

    add_lsp_arguments(
        sub.add_parser("lsp", help="optional read-only OCF YAML/JSON language server over stdio")
    )
    from .narration_cli import add_commands as add_narration_commands

    add_narration_commands(sub)
    art = sub.add_parser(
        "artwork",
        help="original candidate OCF brand, independent themes and offline localized covers",
    )
    art_sub = art.add_subparsers(dest="artwork_kind", required=True)
    art_sub.add_parser("themes")
    import_cmd = art_sub.add_parser(
        "import-review",
        help="verify supplied Cosmic Path assets or create their offline comparison",
    )
    import_cmd.add_argument("--output", type=Path)
    import_cmd.add_argument("--check", action="store_true")
    import_cmd.add_argument("--ui-theme")
    import_cmd.add_argument("--artwork-theme")
    refinement_cmd = art_sub.add_parser(
        "refine",
        help="create a new baseline/refined comparison gallery; never overwrite an existing gallery",
    )
    refinement_cmd.add_argument("--output", type=Path, required=True)
    refinement_cmd.add_argument(
        "--vector-only",
        action="store_true",
        help="portable SVG sources/gallery without binary previews",
    )
    refinement_cmd.add_argument(
        "--check", action="store_true", help="verify existing gallery inputs and checksums"
    )
    refinement_cmd.add_argument("--ui-theme", default="ocf-light")
    refinement_cmd.add_argument(
        "--custom-theme", help="optional custom artwork theme extending an ocf-refined theme"
    )
    gallery_cmd = art_sub.add_parser(
        "gallery",
        help="create a local offline candidate review UI with independent interface/artwork themes",
    )
    gallery_cmd.add_argument("--output", type=Path, required=True)
    gallery_cmd.add_argument("--ui-theme")
    gallery_cmd.add_argument("--artwork-theme")
    brand_cmd = art_sub.add_parser("brand", help="export an original candidate vector variant")
    brand_cmd.add_argument("--variant", default="primary")
    brand_cmd.add_argument("--theme")
    brand_cmd.add_argument("--output", type=Path, required=True)
    brand_cmd.add_argument(
        "--resolution", type=int, default=1000, help="raster width; refined icons allow 32 pixels"
    )
    theme_cmd = art_sub.add_parser(
        "theme", help="validate/resolve a built-in or custom theme; emit independent surface tokens"
    )
    theme_cmd.add_argument("--theme")
    theme_cmd.add_argument("--surface", choices=["ui", "artwork", "documentation"], default="ui")
    cover_cmd = art_sub.add_parser(
        "generate", help="create a candidate localized PNG/JPEG cover, never publication approval"
    )
    cover_cmd.add_argument("function_id")
    cover_cmd.add_argument("--locale", default="en-US")
    cover_cmd.add_argument("--theme")
    cover_cmd.add_argument("--resolution", type=int, default=1400)
    cover_cmd.add_argument("--format", choices=["png", "jpeg"], default="png")
    cover_cmd.add_argument("--version")
    cover_cmd.add_argument("--font", help="explicit installed licensed TTF/OTF override")
    cover_cmd.add_argument("--output", type=Path)
    dev = sub.add_parser(
        "dev",
        help="compact provider-neutral tools and persistent jobs (same services as optional MCP)",
    )
    dev.add_argument(
        "operation", help="allowlisted ocf_* operation; ocf_project_overview lists tools"
    )
    dev.add_argument("--arguments", default="{}", help="JSON object of typed operation arguments")
    sub.add_parser("mcp", help="start optional local stdio MCP server")
    docs_cmd = sub.add_parser("docs-inventory", help="inventory tracked documentation surfaces")
    docs_cmd.add_argument("--check", action="store_true")

    sub.add_parser("help", help="show help")
    capabilities = sub.add_parser("capabilities", help="machine-readable live CLI discovery")
    capabilities.add_argument("--json", action="store_true")
    workspace = sub.add_parser("workspace", help="clean OCF-owned local scratch safely")
    workspace_sub = workspace.add_subparsers(dest="workspace_kind", required=True)
    workspace_clean = workspace_sub.add_parser(
        "clean", help="remove stale marked scratch directories under OCF_WORK_DIR/tmp"
    )
    workspace_clean.add_argument("--older-than-hours", type=float, default=24.0)
    workspace_clean.add_argument("--dry-run", action="store_true")
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
    function_lookup = function_sub.add_parser(
        "lookup",
        help="find current presentation by a historical name or phrase; never selects activation",
    )
    function_lookup.add_argument("query")
    function_lookup.add_argument("--locale", default="en-US")
    function_lookup.add_argument("--json", action="store_true")

    commands = sub.add_parser("commands", help="localized command documentation and export")
    command_sub = commands.add_subparsers(dest="command_kind", required=True)
    command_list = command_sub.add_parser(
        "list", help="list primary function commands (use --all-roles for all)"
    )
    command_list.add_argument("--locale")
    command_list.add_argument("--json", action="store_true")
    command_list.add_argument(
        "--all-roles", action="store_true", help="list all command roles, not just primary"
    )
    command_describe = command_sub.add_parser("describe", help="describe one function's commands")
    command_describe.add_argument("function")
    command_describe.add_argument("--locale")
    command_describe.add_argument("--json", action="store_true")
    command_export = command_sub.add_parser("export", help="export the localized command guide")
    command_export.add_argument("--locale")
    command_export.add_argument("--format", choices=["json", "md"], default="json")
    command_export.add_argument("--output")
    command_export.add_argument("--force", action="store_true")

    from .editorial import add_parser as add_content_parser

    add_content_parser(sub)

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
    from .voice_engine_cli import add_new_commands

    add_new_commands(new_sub)
    new_sub.add_parser("function", help="new function record")
    new_sub.add_parser("proposal", help="new proposal")
    new_sub.add_parser("audio", help="new audio implementation manifest")
    new_sub.add_parser("background", help="new background preset manifest")
    new_sub.add_parser("test-report", help="new testing report")
    new_sub.add_parser(
        "voice", help="privately import a supported model through the voice profile wizard"
    )
    new_sub.add_parser(
        "session-plan", help="generate a complete session plan from existing narration"
    )

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
    validate.add_argument(
        "--json",
        action="store_true",
        help="structured diagnostics from the same authoritative validators",
    )

    build = sub.add_parser("build-index", help="regenerate derived indexes")
    build.add_argument("--check", action="store_true", help="fail if indexes are stale")

    review = sub.add_parser("review", help="command review tooling")
    review_sub = review.add_subparsers(dest="review_kind")
    review_sub.add_parser("commands", help="lint commands and print the review report")

    audio = sub.add_parser("audio", help="audio tooling")
    audio_sub = audio.add_subparsers(dest="audio_kind")
    review_sessions_cmd = audio_sub.add_parser(
        "review-sessions",
        help="compare 1..8 actual session bindings; optional short exact-sentence speech excerpts",
    )
    review_sessions_cmd.add_argument("function_ids", nargs="+")
    review_sessions_cmd.add_argument("--locale", default="en-US")
    review_sessions_cmd.add_argument(
        "--voice", help="explicitly synthesize short excerpts with this voice"
    )
    bulk_cmd = audio_sub.add_parser(
        "render-many",
        help="explicit resumable bulk complete-session auditions (one memory-bounded job at a time)",
    )
    bulk_cmd.add_argument("function_ids", nargs="*")
    bulk_cmd.add_argument("--all", action="store_true")
    bulk_cmd.add_argument("--locale", default="en-US")
    bulk_cmd.add_argument("--voice", required=True)
    bulk_cmd.add_argument("--pacing", choices=["normal", "relaxed", "sleep"], default="sleep")
    bulk_cmd.add_argument("--rate", type=int, default=44100)
    bulk_cmd.add_argument("--dry-run", action="store_true")
    bulk_cmd.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="skip only checksum-verified matching renders (default)",
    )
    bulk_cmd.add_argument(
        "--force", action="store_true", help="create new auditions even if verified outputs exist"
    )
    plan_cmd = audio_sub.add_parser(
        "plan", help="generate compact voice-independent complete-session source plans"
    )
    plan_cmd.add_argument("function_id", nargs="?")
    plan_cmd.add_argument("--all", action="store_true")
    plan_cmd.add_argument("--locale", default="en-US")
    plan_cmd.add_argument(
        "--overrides", type=Path, help="explicit JSON session overrides; preview with --expand"
    )
    plan_cmd.add_argument(
        "--output", type=Path, help="source-plan root (default audio/session-plans)"
    )
    plan_mode = plan_cmd.add_mutually_exclusive_group()
    plan_mode.add_argument("--dry-run", action="store_true")
    plan_mode.add_argument("--check", action="store_true")
    plan_cmd.add_argument(
        "--expand",
        action="store_true",
        help="print expanded single-function pacing/DSP preview without writing",
    )
    migrate_cmd = audio_sub.add_parser(
        "migrate-bindings",
        help="explicitly bind existing HPlus narration to shared sessions; preserve custom bindings",
    )
    migrate_cmd.add_argument("function_ids", nargs="*")
    migrate_cmd.add_argument("--all", action="store_true")
    migrate_cmd.add_argument("--dry-run", action="store_true")
    eligibility_cmd = audio_sub.add_parser(
        "eligibility",
        help="derive complete-session TTS eligibility independently of historical sources",
    )
    eligibility_cmd.add_argument("function_id", nargs="?")
    eligibility_cmd.add_argument("--all", action="store_true")
    eligibility_cmd.add_argument("--locale", default="en-US")
    eligibility_cmd.add_argument("--output", help="write deterministic migration report JSON")
    defaults_cmd = audio_sub.add_parser(
        "defaults", help="verify the immutable shared audio defaults lock"
    )
    defaults_cmd.add_argument(
        "--create-lock", action="store_true", help="create the initial lock; refuses replacement"
    )
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
    narration_render = audio_sub.add_parser(
        "render", help="render a complete bound session or explicit narration-only audition"
    )
    narration_render.add_argument("function_id", help="canonical function ID")
    narration_render.add_argument(
        "--mode",
        choices=["session", "narration-only"],
        default="session",
        help="complete template session by default; choose narration-only explicitly",
    )
    narration_render.add_argument("--locale", help="requested BCP-47 locale")
    narration_render.add_argument(
        "--narration-sources", type=Path, help="explicit recorded/hybrid source manifest"
    )
    narration_render.add_argument(
        "--narration-source", choices=("tts", "recording", "hybrid", "silence")
    )
    narration_render.add_argument(
        "--voice", help="voice profile ID/slug; otherwise explicit function/template selection"
    )
    narration_render.add_argument(
        "--overrides",
        type=Path,
        help="explicit JSON session overrides, higher priority than function bindings",
    )
    narration_render.add_argument(
        "--pacing", choices=["normal", "relaxed", "sleep"], default="normal"
    )
    narration_render.add_argument(
        "--template", help="complete session template ID (must be bound to the function)"
    )
    narration_render.add_argument(
        "--dsp-profile", help="explicit state/background profile override"
    )
    narration_render.add_argument("--output", help="new audition directory (never overwritten)")
    narration_render.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    narration_render.add_argument(
        "--mix-profile",
        type=Path,
        help="explicit linked-stereo ducking/headroom/limiter configuration",
    )
    narration_render.add_argument(
        "--voice-gain",
        type=float,
        default=None,
        help="linear narration gain (overrides function configuration)",
    )
    narration_render.add_argument(
        "--background-gain",
        type=float,
        help="linear background gain (default 1.0 for calibrated state profiles)",
    )
    narration_render.add_argument(
        "--dry-run", action="store_true", help="print the resolved TTS plan"
    )
    mix = audio_sub.add_parser("mix", help="mix narration with background audio")
    mix.add_argument("--speech", required=True, help="narration WAV")
    mix.add_argument("--background", help="optional background WAV")
    mix.add_argument("--output", required=True, help="mixed WAV path")
    mix.add_argument("--background-gain", type=float, default=0.25, help="background level (0-1)")
    mix.add_argument("--force", action="store_true", help="overwrite an existing file")
    mix.add_argument("--mix-profile", type=Path)
    build_cmd = audio_sub.add_parser("build", help="build a mastered audio implementation")
    build_cmd.add_argument("query", help="audio implementation id or manifest path")
    build_cmd.add_argument("--mix-profile", type=Path)
    build_cmd.add_argument(
        "--format",
        action="append",
        choices=["wav", "flac", "mp3"],
        default=None,
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
    build_cmd.add_argument("--output", help="output directory (default .ocf-work/renders)")
    build_cmd.add_argument("--rate", type=int, default=44100, help="sample rate (Hz)")
    build_cmd.add_argument("--voice-gain", type=float, default=1.0, help="linear narration gain")
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
    release_cmd = audio_sub.add_parser(
        "release", help="render, verify, and package a localized function release"
    )
    release_cmd.add_argument("query", help="audio implementation ID or function ID")
    release_cmd.add_argument("--locale", help="requested BCP-47 locale (default canonical locale)")
    release_cmd.add_argument(
        "--format",
        action="append",
        choices=["mp3", "flac"],
        default=None,
        help="release format(s), repeatable (default: flac and mp3)",
    )
    release_cmd.add_argument("--voice", help="voice profile ID/slug or backend name")
    release_cmd.add_argument(
        "--artwork", help="explicit PNG/JPEG cover; takes precedence over generated artwork"
    )
    release_cmd.add_argument(
        "--artwork-theme", help="explicitly select an original candidate OCF generated cover"
    )
    release_cmd.add_argument("--artwork-resolution", type=int, default=1400)
    release_cmd.add_argument("--output", help="release root directory (default: releases/)")
    release_cmd.add_argument("--version", help="explicit release version")
    release_cmd.add_argument(
        "--tag", action="append", default=[], help="metadata override KEY=VALUE"
    )
    release_cmd.add_argument(
        "--dry-run", action="store_true", help="show planned paths without rendering"
    )
    release_cmd.add_argument(
        "--force", action="store_true", help="replace an existing release directory"
    )
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
    from .voice_engine_cli import add_commands as add_voice_engine_commands

    add_voice_engine_commands(voice_sub)
    inspect_voice = voice_sub.add_parser(
        "inspect", help="inspect a built-in or private reusable voice profile"
    )
    inspect_voice.add_argument("voice_id")
    profile_validate = voice_sub.add_parser(
        "validate-profile", help="validate portable profile metadata and installed model checksums"
    )
    profile_validate.add_argument("file", type=Path)
    profile_validate.add_argument("--metadata-only", action="store_true")
    model_import = voice_sub.add_parser(
        "import-model",
        help="import an existing local Piper ONNX model privately; never train or publish",
    )
    model_import.add_argument("file", type=Path)
    model_import.add_argument("--id", required=True)
    model_import.add_argument("--name", required=True)
    model_import.add_argument("--model-version", default="unversioned-local")
    model_import.add_argument("--license", default="unknown")
    model_import.add_argument(
        "--kind", choices=["installed-model", "custom", "cloned"], default="installed-model"
    )
    model_import.add_argument(
        "--consent",
        choices=["unknown", "self-recorded", "authorized-contributor"],
        default="unknown",
    )
    model_import.add_argument("--consent-record")
    dataset_init = voice_sub.add_parser(
        "dataset-init",
        help="create original recording prompts and a private manifest; no microphone capture",
    )
    dataset_init.add_argument("directory", type=Path)
    dataset_init.add_argument("--id", default="my-voice")
    dataset_init.add_argument("--rate", type=int, default=22050)
    dataset_validate = voice_sub.add_parser(
        "validate-dataset", help="validate local PCM recordings, transcripts, splits and quality"
    )
    dataset_validate.add_argument("file", type=Path)
    training_plan = voice_sub.add_parser(
        "training-plan", help="report evaluated adapters and unverified training blockers honestly"
    )
    training_plan.add_argument("--dataset", type=Path)
    training_plan.add_argument("--backend", choices=["piper", "f5-tts"], default="piper")
    voice_audition = voice_sub.add_parser(
        "audition", help="explicitly synthesize original short passages for 1..4 voices"
    )
    voice_audition.add_argument("voices", nargs="+")
    voice_audition.add_argument("--locale", default="en-US")
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
        "--pacing-profile",
        help="override the template's versioned pacing policy",
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
    else:
        result = validate_all()
    if getattr(args, "json", False):
        import json
        from dataclasses import asdict

        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "errors": len(result.errors),
                    "warnings": len(result.warnings),
                    "diagnostics": [asdict(issue) for issue in result.issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result.ok else 1
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
                    Path(issue.target or "").is_relative_to(Path(path)) for path in paths
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
        if exc.code:
            print(HELP_TEXT)
        return int(exc.code or 0)

    try:
        if args.command == "artwork":
            import json

            from . import artwork

            if args.artwork_kind == "themes":
                result = {
                    "themes": [p.stem for p in sorted((artwork.BRAND / "themes").glob("*.json"))],
                    "brand": artwork.identity(),
                }
            elif args.artwork_kind == "import-review":
                from .brand_import import comparison_gallery, verify

                result = (
                    comparison_gallery(
                        args.output,
                        check=args.check,
                        ui_theme=args.ui_theme,
                        artwork_theme=args.artwork_theme,
                    )
                    if args.output
                    else verify()
                )
            elif args.artwork_kind == "refine":
                from .brand_refinement import comparison_gallery

                result = comparison_gallery(
                    args.output,
                    vector_only=args.vector_only,
                    ui_theme=args.ui_theme,
                    custom_theme=args.custom_theme,
                    check=args.check,
                )
            elif args.artwork_kind == "brand":
                result = artwork.export_brand(
                    args.output, variant=args.variant, theme=args.theme, resolution=args.resolution
                )
            elif args.artwork_kind == "gallery":
                result = artwork.gallery(
                    args.output, ui_theme=args.ui_theme, artwork_theme=args.artwork_theme
                )
            elif args.artwork_kind == "theme":
                result = artwork.theme_tokens(args.surface, args.theme)
            else:
                result = artwork.generate_cover(
                    args.function_id,
                    locale=args.locale,
                    theme=args.theme,
                    resolution=args.resolution,
                    format=args.format,
                    version=args.version,
                    overrides={"font": args.font} if args.font else None,
                    output=args.output,
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "dev":
            import json

            from .agent_api import dispatch

            try:
                arguments = json.loads(args.arguments)
            except ValueError as exc:
                raise OCFError("--arguments must be valid JSON") from exc
            if not isinstance(arguments, dict):
                raise OCFError("--arguments must be a JSON object")
            result = dispatch(args.operation, arguments)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 1 if result.get("status") == "failed" else 0
        if args.command == "lsp":
            from .lsp_server import run

            return run(args)
        if args.command == "mcp":
            from .mcp_server import main as mcp_main

            mcp_main()
            return 0
        if args.command == "docs-inventory":
            from .doc_inventory import main as inventory_main

            return inventory_main(["--check"] if args.check else [])
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
        if args.command == "workspace" and args.workspace_kind == "clean":
            import math

            from .paths import cleanup_workspace

            if not math.isfinite(args.older_than_hours) or args.older_than_hours < 0:
                raise OCFError("--older-than-hours must be finite and nonnegative")
            candidates = cleanup_workspace(args.older_than_hours * 3600, dry_run=args.dry_run)
            action = "Would clean" if args.dry_run else "Cleaned"
            for path in candidates:
                print(f"{action} {path}")
            if not candidates:
                print("No stale OCF scratch directories found.")
            return 0
        if args.command == "functions":
            import json

            if args.function_kind == "lookup":
                from .vocabulary import lookup

                rows = lookup(args.query, locale=args.locale)
                if args.json:
                    print(
                        json.dumps(
                            {"locale": args.locale, "matches": rows, "activation_selected": False},
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    for row in rows:
                        cue = row["cue"] or {}
                        print(
                            f"{row['function_id']}: {row['title']} — {cue.get('display_cue', '')} — lookup match: "
                            + ", ".join(item["kind"] for item in row["matches"])
                        )
                return 0

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
        if args.command == "content":
            from .editorial import run as run_content

            return run_content(args)
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
            if args.new_kind == "voice-dataset":
                import json

                from .voice_engine_cli import dispatch

                print(json.dumps(dispatch(args), ensure_ascii=False, indent=2))
                return 0
            if args.new_kind == "function":
                run_function_wizard()
            elif args.new_kind == "proposal":
                run_proposal_wizard()
            elif args.new_kind == "audio":
                run_audio_wizard()
            elif args.new_kind == "background":
                run_background_wizard()
            elif args.new_kind == "session-plan":
                from .prompts import run_session_plan_wizard

                run_session_plan_wizard()
            elif args.new_kind == "voice":
                from .prompts import run_voice_profile_wizard

                run_voice_profile_wizard()
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
        if args.command == "commands":
            from .command_docs import run_cli

            return run_cli(args)
        if args.command == "review" and args.review_kind == "commands":
            return cmd_review_commands()
        if args.command == "audio":
            if args.audio_kind == "review-sessions":
                import json

                from .session_review import review_sessions

                print(
                    json.dumps(
                        review_sessions(args.function_ids, locale=args.locale, voice=args.voice),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if args.audio_kind == "defaults":
                import json

                from .audio_defaults import check_lock, create_lock

                if args.create_lock:
                    create_lock()
                print(json.dumps(check_lock(), indent=2, ensure_ascii=False))
                return 0
            if args.audio_kind == "render-many":
                import json

                from .bulk_render import render_many

                if bool(args.function_ids) == args.all:
                    raise OCFError("select function IDs or --all")
                result = render_many(
                    None if args.all else args.function_ids,
                    voice=args.voice,
                    locale=args.locale,
                    pacing=args.pacing,
                    dry_run=args.dry_run,
                    force=args.force,
                    resume=args.resume,
                    sample_rate=args.rate,
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1 if result["failed"] else 0
            if args.audio_kind == "plan":
                import json

                from .session_plans import generate_plans, source_plan

                if bool(args.function_id) == args.all:
                    raise OCFError("select FUNCTION_ID or --all")
                if args.expand:
                    if args.all or args.check:
                        raise OCFError("--expand requires a single function and cannot use --check")
                    if args.overrides:
                        from .complete_session import build_complete_session_plan

                        result = build_complete_session_plan(
                            args.function_id,
                            locale=args.locale,
                            overrides=read_json_object(args.overrides),
                        )
                    else:
                        result = source_plan(args.function_id, args.locale)[2]
                else:
                    if args.overrides:
                        raise OCFError(
                            "use --expand for ephemeral CLI overrides; persist deliberate function overrides in its binding for generation"
                        )
                    result = generate_plans(
                        None if args.all else [args.function_id],
                        locale=args.locale,
                        output=args.output,
                        check=args.check,
                        dry_run=args.dry_run,
                    )
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            if args.audio_kind in {"migrate-bindings", "eligibility"}:
                import json

                from .eligibility import eligibility, migrate_bindings, migration_report

                if args.audio_kind == "migrate-bindings":
                    if bool(args.function_ids) == args.all:
                        raise OCFError("select function IDs or --all")
                    ids = [r.id for r in load_all_functions()] if args.all else args.function_ids
                    result = migrate_bindings(ids, dry_run=args.dry_run)
                else:
                    if bool(args.function_id) == args.all:
                        raise OCFError("select FUNCTION_ID or --all")
                    result = (
                        migration_report(args.locale)
                        if args.all
                        else eligibility(args.function_id, args.locale)
                    )
                text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                if getattr(args, "output", None):
                    from .utils import write_text_atomic

                    write_text_atomic(Path(args.output), text)
                print(text, end="")
                return (
                    0
                    if args.audio_kind == "migrate-bindings"
                    or (result.get("tts_renderable") == result.get("total", True))
                    else 1
                )
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
            if args.audio_kind == "render":
                import json

                if args.mode == "narration-only":
                    from .narration_first import render_narration_first

                    if (
                        args.overrides
                        or args.narration_sources
                        or args.narration_source
                        or args.mix_profile
                        or not args.voice
                    ):
                        raise OCFError(
                            "narration-only requires --voice and does not apply complete-session overrides"
                        )

                    result = render_narration_first(
                        args.function_id,
                        locale=args.locale,
                        voice=args.voice,
                        pacing=args.pacing,
                        output=args.output,
                        dry_run=args.dry_run,
                        sample_rate=args.rate,
                    )
                else:
                    from .complete_session import render_complete_session

                    result = render_complete_session(
                        args.function_id,
                        locale=args.locale,
                        voice=args.voice,
                        pacing=args.pacing,
                        template=args.template,
                        dsp_profile=args.dsp_profile,
                        overrides=read_json_object(args.overrides) if args.overrides else None,
                        voice_gain=args.voice_gain,
                        background_gain=args.background_gain,
                        **(
                            {"mix_profile": args.mix_profile}
                            if args.mix_profile is not None
                            else {}
                        ),
                        output=args.output,
                        dry_run=args.dry_run,
                        sample_rate=args.rate,
                        **(
                            {
                                "narration_sources": args.narration_sources,
                                "narration_source": args.narration_source,
                            }
                            if args.narration_sources is not None
                            or args.narration_source is not None
                            else {}
                        ),
                    )
                if args.dry_run:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    manifest = result["manifest"]
                    print(
                        json.dumps(
                            {
                                "output_directory": result["output_directory"],
                                "artifacts": manifest["artifacts"],
                                "measurements": manifest["measurements"],
                                "approval_state": manifest["approval_state"],
                                "release_ready": manifest["release_ready"],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                return 0
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
                if args.mix_profile is not None:
                    import json

                    from .mix_profiles import mix_master

                    target = Path(args.output)
                    if target.exists() and not args.force:
                        raise OCFError("refusing to overwrite existing mix; use --force")
                    receipt = mix_master(
                        Path(args.speech),
                        Path(args.background) if args.background else None,
                        target,
                        mix_profile=args.mix_profile,
                        sample_rate=44100,
                        background_gain=args.background_gain,
                    )
                    print(json.dumps(receipt, indent=2))
                    return 0
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
                    formats=args.format or ["wav", "flac", "mp3"],
                    tag_overrides=tag_overrides,
                    voice=args.voice,
                    background_gain=args.background_gain,
                    sample_rate=args.rate,
                    overwrite=args.force,
                    fit=bool(getattr(args, "fit", False)),
                    flow=bool(getattr(args, "flow", False)),
                    even_counts=bool(getattr(args, "even_counts", False)),
                    dsp_profile=getattr(args, "dsp_profile", None),
                    voice_gain=getattr(args, "voice_gain", 1.0),
                    recordings=getattr(args, "recordings", None),
                    locale=getattr(args, "locale", None),
                    strict=not getattr(args, "allow_fallback", False),
                    **({"mix_profile": args.mix_profile} if args.mix_profile is not None else {}),
                )
                return 0
            if args.audio_kind == "release":
                import json

                from .release import package_release

                metadata_overrides: dict[str, str] = {}
                for spec in args.tag:
                    if "=" not in spec:
                        raise OCFError(f"--tag expects KEY=VALUE, got {spec!r}")
                    key, value = spec.split("=", 1)
                    if not key.strip():
                        raise OCFError("--tag key cannot be empty")
                    metadata_overrides[key.strip()] = value.strip()
                result = package_release(
                    args.query,
                    locale=args.locale,
                    formats=args.format,
                    voice=args.voice,
                    artwork=args.artwork,
                    **(
                        {
                            "artwork_theme": args.artwork_theme,
                            "artwork_resolution": args.artwork_resolution,
                        }
                        if args.artwork_theme
                        else {}
                    ),
                    output=args.output,
                    version=args.version,
                    metadata_overrides=metadata_overrides,
                    dry_run=args.dry_run,
                    overwrite=args.force,
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            if args.audio_kind == "inspect":
                from .audio_build import inspect as inspect_file
                from .utils import yaml_safe_dump

                print(yaml_safe_dump(inspect_file(args.file)).rstrip())
                return 0
            print(HELP_TEXT)
            return 0
        if args.command == "narration":
            import json

            from .narration_cli import dispatch

            print(json.dumps(dispatch(args), ensure_ascii=False, indent=2))
            return 0
        if args.command == "voice":
            if args.voice_kind in {
                "capabilities",
                "export-profile",
                "import-profile",
                "dataset-record",
                "dataset-guide",
            }:
                import json

                from .voice_engine_cli import dispatch

                result = dispatch(args)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1 if result.get("status") == "failed" else 0
            if args.voice_kind in {
                "inspect",
                "validate-profile",
                "import-model",
                "dataset-init",
                "validate-dataset",
                "training-plan",
                "audition",
            }:
                import json

                from . import custom_voices, voice_datasets
                from .indexes import load_voice_profiles, load_yaml_file

                if args.voice_kind == "inspect":
                    result = next(
                        (
                            p
                            for p in load_voice_profiles()
                            if p["id"] == args.voice_id or p["slug"] == args.voice_id
                        ),
                        None,
                    )
                    if result is None:
                        raise OCFError("unknown voice profile")
                elif args.voice_kind == "validate-profile":
                    result = custom_voices.validate_profile(
                        load_yaml_file(args.file), assets=not args.metadata_only
                    )
                elif args.voice_kind == "import-model":
                    result = custom_voices.import_model(
                        args.file,
                        voice_id=args.id,
                        name=args.name,
                        model_version=args.model_version,
                        license=args.license,
                        voice_kind=args.kind,
                        consent_status=args.consent,
                        consent_record=args.consent_record,
                    )
                elif args.voice_kind == "dataset-init":
                    result = voice_datasets.initialize(
                        args.directory, dataset_id=args.id, sample_rate=args.rate
                    )
                elif args.voice_kind == "validate-dataset":
                    result = voice_datasets.validate_dataset(args.file)
                elif args.voice_kind == "training-plan":
                    result = voice_datasets.training_plan(args.dataset, backend=args.backend)
                else:
                    result = custom_voices.audition(args.voices, locale=args.locale)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1 if result.get("status") == "failed" else 0
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
                from .utils import read_text

                try:
                    mapping = json.loads(
                        read_text(Path(args.mapping)), object_pairs_hook=unique_mapping
                    )
                except json.JSONDecodeError as exc:
                    raise OCFError(f"invalid recording mapping JSON: {exc}") from exc
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
            # All other registered kinds return above; the remaining kind is
            # pseudo. Unknown kinds exit during argparse validation.
            return cmd_locale_pseudo(args)
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
