"""Voice capability/profile CLI adapters and an import-first recording wizard.

The shared CLI owns rendering and exit codes. Register these hooks on its existing
subparsers, then pass matching namespaces to ``dispatch``.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from . import custom_voices, voice_capabilities, voice_datasets
from .utils import OCFError


def add_commands(voice_subparsers) -> None:
    """Register additional ``voice`` commands (the shared dest is ``voice_kind``)."""
    capabilities = voice_subparsers.add_parser(
        "capabilities", help="report local voice adapters, upstream features and unsupported paths"
    )
    capabilities.add_argument(
        "--gpu", action="store_true", help="explicitly request a bounded local GPU query"
    )
    capabilities.add_argument("--json", action="store_true")

    export = voice_subparsers.add_parser(
        "export-profile", help="export portable metadata; asset copying is opt-in"
    )
    export.add_argument("query", metavar="QUERY", help="unambiguous voice ID, slug or name")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--include-assets", action="store_true")

    profile_import = voice_subparsers.add_parser(
        "import-profile", help="import a portable profile privately; asset copying is opt-in"
    )
    profile_import.add_argument("file", metavar="FILE", type=Path)
    profile_import.add_argument("--include-assets", action="store_true")
    profile_import.add_argument("--id", help="new private voice ID")
    profile_import.add_argument("--consent-record", help="local portable consent reference")

    pack_create = voice_subparsers.add_parser(
        "create-pack", help="create a private reference-based voice pack from a prepared WAV"
    )
    pack_create.add_argument("--reference", type=Path, required=True)
    pack_create.add_argument("--id", required=True)
    pack_create.add_argument("--name", required=True)
    pack_create.add_argument("--locale", default="en-US")
    pack_create.add_argument("--transcript", required=True, help="exact confirmed reference words")
    pack_create.add_argument("--consent-declaration", required=True)
    pack_create.add_argument(
        "--source-type",
        choices=("original-recording", "generated-tts", "authorized-other"),
        default="original-recording",
    )

    pack_inspect = voice_subparsers.add_parser(
        "inspect-pack", help="validate and inspect a private OCF reference voice pack"
    )
    pack_inspect.add_argument("voice_id")

    pack_audition = voice_subparsers.add_parser(
        "audition-pack", help="synthesize new text with a private reference voice pack"
    )
    pack_audition.add_argument("voice_id")
    pack_audition.add_argument("--text", required=True)
    pack_audition.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")

    prepare = voice_subparsers.add_parser(
        "prepare-reference", help="inspect and prepare a local WAV/FLAC/MP3 reference clip"
    )
    prepare.add_argument("sample", type=Path)
    prepare.add_argument("--start", type=float)
    prepare.add_argument("--duration", type=float)

    recording = voice_subparsers.add_parser(
        "dataset-record", help="import an externally recorded WAV into one dataset prompt slot"
    )
    recording.add_argument("manifest", metavar="MANIFEST", type=Path)
    recording.add_argument("prompt", metavar="PROMPT")
    recording.add_argument("--audio", metavar="SOURCE", type=Path, required=True)
    recording.add_argument("--session", metavar="ID", required=True)
    recording.add_argument("--speaker", metavar="ID", required=True)

    guide = voice_subparsers.add_parser(
        "dataset-guide", help="show recording setup, exact script slots and dataset readiness"
    )
    guide.add_argument("manifest", metavar="MANIFEST", type=Path)
    guide.add_argument("--json", action="store_true")


def add_new_commands(new_subparsers) -> None:
    """Add ``new voice-dataset MANIFEST`` alongside the existing ``new voice``."""
    wizard = new_subparsers.add_parser(
        "voice-dataset", help="guide setup and per-prompt file imports into an existing dataset"
    )
    wizard.add_argument("manifest", metavar="MANIFEST", type=Path)


def capabilities_report(*, probe_gpu: bool = False) -> dict:
    """Keep installed packages, shipped adapters and verified inference distinct."""
    backends = []
    for backend in voice_capabilities.capability_registry():
        capability = voice_capabilities.backend_capability(backend)
        blockers, actions = [], []
        if not capability["ocf"]["inference_supported"]:
            blockers.append("OCF inference is unsupported for this backend.")
            actions.append(
                "Use a supported Piper/eSpeak adapter for OCF inference; installing this package "
                "does not enable an OCF adapter."
            )
        elif not capability["available"]:
            blockers.append("The required local inference executable is missing.")
            if backend == "chatterbox-nano":
                actions.append("Install the optional environment from docs/VOICE_PACKS.md.")
            else:
                actions.append(
                    f"Install {capability['binary']} locally, then run ocf voice doctor and an explicit "
                    "ocf voice audition with a compatible profile."
                )
        else:
            actions.append(
                "Run ocf voice doctor and ocf voice audition PROFILE to verify inference."
            )
        if not capability["ocf"]["training_supported"]:
            blockers.append("OCF training is unsupported until a training adapter is verified.")
            actions.append(
                "Run ocf voice training-plan with an authorized dataset to inspect blockers "
                "and the upstream guide; no OCF train/clone command is available."
            )
        if backend == "chatterbox-nano" and capability["available"]:
            actions.append(
                "First inference downloads the upstream model into the local workspace cache; "
                "use voice audition-pack with an explicitly authorized reference."
            )
        backends.append(
            {
                **capability,
                "inference_verified": False,
                "blockers": blockers,
                "next_actions": actions,
            }
        )
    return {
        "backends": backends,
        "resources": voice_capabilities.local_preflight(probe_gpu=probe_gpu),
        "training_supported": any(b["ocf"]["training_supported"] for b in backends),
        "inference_verified": False,
        "next_actions": [
            "Use ocf voice dataset-init DIRECTORY, then ocf voice dataset-guide MANIFEST "
            "to prepare local recording imports."
        ],
    }


def dispatch(args: Namespace) -> dict:
    """Return service data for registered commands; the caller formats the result."""
    if (
        getattr(args, "command", None) == "new"
        and getattr(args, "new_kind", None) == "voice-dataset"
    ):
        return run_recording_wizard(args.manifest)
    kind = getattr(args, "voice_kind", None)
    if kind == "capabilities":
        return capabilities_report(probe_gpu=args.gpu)
    if kind == "export-profile":
        return custom_voices.export_profile(
            args.query, args.output, include_assets=args.include_assets
        )
    if kind == "import-profile":
        return custom_voices.import_profile(
            args.file,
            include_assets=args.include_assets,
            voice_id=args.id,
            consent_record=args.consent_record,
        )
    if kind == "create-pack":
        from .voice_packs import create_pack

        return create_pack(
            args.reference,
            voice_id=args.id,
            name=args.name,
            locale=args.locale,
            transcript=args.transcript,
            consent_declaration=args.consent_declaration,
            source_type=args.source_type,
        )
    if kind == "inspect-pack":
        from .voice_packs import inspect_pack

        return inspect_pack(args.voice_id)
    if kind == "audition-pack":
        from .voice_packs import synthesize

        return synthesize(args.voice_id, args.text, device=args.device)
    if kind == "prepare-reference":
        from .voice_packs import prepare_reference

        return prepare_reference(args.sample, start_s=args.start, duration_s=args.duration)
    if kind == "dataset-record":
        return voice_datasets.import_recording(
            args.manifest,
            args.prompt,
            args.audio,
            session_id=args.session,
            speaker=args.speaker,
        )
    if kind == "dataset-guide":
        return voice_datasets.recording_workflow(args.manifest)
    raise OCFError(f"unknown voice engine command: {kind}")


def run_recording_wizard(manifest, input_fn=input, print_fn=print) -> dict:
    """Guide external recording imports; never open a microphone or synthesize speech.

    Blank file paths skip a slot; ``:quit`` or interrupted input retains successful
    imports. Import errors allow retrying the slot. Exact transcripts, session
    metadata and audio validation remain owned by the dataset service.
    """
    manifest = Path(manifest).expanduser()
    workflow = voice_datasets.recording_workflow(manifest)
    imports, skipped, errors = [], [], []
    cancelled = False

    def required(label):
        while True:
            value = input_fn(label).strip()
            if value:
                return value
            print_fn("A nonempty identity is required.")

    print_fn("Import-first recording: record externally, then import each exact prompt's WAV.")
    print_fn("No microphone capture, conversion, model inference or training is performed.")
    print_fn(f"Required audio: mono PCM16 WAV at {workflow['sample_rate']} Hz.")
    for guidance in workflow["guidance"]:
        print_fn(guidance)
    print_fn("Leave a file path blank to skip; enter :quit to finish and keep prior imports.")
    try:
        setup = {
            "room_notes": input_fn("Room setup / room-tone notes (optional): ").strip(),
            "microphone": input_fn("Microphone / distance / position (optional): ").strip(),
            "gain_notes": input_fn("Input gain / peak check (optional): ").strip(),
        }
        metadata = {key: value for key, value in setup.items() if value}
        print_fn("Setup notes are saved with imported sessions; they are not measurements.")
        for prompt in workflow["prompts"]:
            state = "already imported; a new session adds a take" if prompt["imported"] else "empty"
            print_fn(f"\n{prompt['id']} [{prompt['split']}; {state}]")
            print_fn(prompt["text"])
            while True:
                source = input_fn("External WAV path (blank skips, :quit finishes): ").strip()
                if source == ":quit":
                    cancelled = True
                    break
                if not source:
                    skipped.append(prompt["id"])
                    break
                session = required("Session ID (lowercase letters, digits, hyphens): ")
                speaker = required("Speaker ID: ")
                try:
                    result = voice_datasets.import_recording(
                        manifest,
                        prompt["id"],
                        Path(source).expanduser(),
                        session_id=session,
                        speaker=speaker,
                        transcript=prompt["text"],
                        session_metadata=metadata or None,
                    )
                except OCFError as exc:
                    errors.append({"prompt": prompt["id"], "message": str(exc)})
                    print_fn(f"Import failed: {exc}. Retry, skip, or enter :quit.")
                    continue
                imports.append(result)
                print_fn(f"Imported {result['record']['id']}; source preserved.")
                break
            if cancelled:
                break
    except (EOFError, KeyboardInterrupt):
        cancelled = True
        print_fn("Input interrupted; completed imports are retained.")
    final = voice_datasets.recording_workflow(manifest)
    print_fn(f"Imported {len(imports)} take(s); skipped {len(skipped)} slot(s).")
    for blocker in final["validation"]["readiness"]["blockers"]:
        print_fn(f"Dataset next step: {blocker}")
    return {
        **final,
        "status": "cancelled" if cancelled else "completed",
        "imports": imports,
        "skipped_prompts": skipped,
        "import_errors": errors,
        "microphone_captured": False,
        "model_produced": False,
    }
