"""Interactive, non-programmer-friendly wizards and prompt helpers.

Every prompt supports ``help`` (``?``), ``skip``, ``back`` (where enabled), and
``quit``. Wizards gather a dict, show a final review screen, then atomically
write the resulting record and validate it immediately.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .indexes import load_all_functions
from .models import DOMAINS
from .paths import (
    AUDIO_MANIFESTS_DIR,
    FUNCTIONS_DIR,
    PROPOSALS_DIR,
    REPO_ROOT,
    TEMPLATES_DIR,
    ensure_dir,
)
from .utils import (
    OCFFileExistsError,
    current_date,
    read_text,
    slugify,
    write_text_atomic,
    yaml_safe_dump,
)
from .validators import print_result, validate_background_manifests, validate_function_file

# ---------------------------------------------------------------------------
# Prompt primitives
# ---------------------------------------------------------------------------

BACK = "__BACK__"
SKIP_CONST = "__SKIP__"
QUIT = "__QUIT__"

DOMAIN_ABBR: dict[str, str] = {
    "foundation": "FND",
    "cognition": "COG",
    "emotion": "EMO",
    "communication": "COM",
    "body": "BOD",
    "performance": "PRF",
    "sensory": "SEN",
    "sleep": "SLP",
    "lifestyle": "LIF",
    "emergency": "EMG",
    "automation": "AUT",
    "experimental": "EXP",
}


@dataclass
class PromptResult:
    value: Any
    intent: str = "value"  # "value" | "back" | "skip" | "quit"


def ask(
    prompt: str,
    *,
    default: str | None = None,
    help_text: str = "",
    choices: list[str] | None = None,
    validator: Callable[[str], str | None] | None = None,
    allow_skip: bool = True,
    allow_back: bool = True,
) -> PromptResult:
    """Ask a single question with controls. Returns PromptResult."""
    suffixes = ["[default: " + default + "]" if default else ""]
    controls = []
    if allow_back:
        controls.append("back")
    if allow_skip:
        controls.append("skip")
    controls.append("quit")
    if controls:
        suffixes.append("(" + ", ".join(controls) + ")")
    full_prompt = f"{prompt} {' '.join(suffixes)}\n> " if default else f"{prompt}\n> "

    while True:
        try:
            raw = input(full_prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return PromptResult(QUIT, "quit")

        lower = raw.lower()
        if lower == "quit":
            return PromptResult(QUIT, "quit")
        if lower == "back" and allow_back:
            return PromptResult(BACK, "back")
        if lower == "skip" and allow_skip:
            return PromptResult(SKIP_CONST, "skip")
        if lower in ("help", "?"):
            print(("  help: " + help_text) if help_text else "  (no help provided for this field)")
            continue
        if not raw and default is not None:
            return PromptResult(default, "value")

        if choices:
            if lower in [c.lower() for c in choices]:
                match = next(c for c in choices if c.lower() == lower)
                return PromptResult(match, "value")
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                return PromptResult(choices[int(raw) - 1], "value")
            print("  Choose one of: " + ", ".join(f"{i + 1} ({c})" for i, c in enumerate(choices)))
            continue

        if validator is not None:
            problem = validator(raw)
            if problem:
                print(f"  {problem}")
                continue
        return PromptResult(raw, "value")


def ask_pick(
    prompt: str,
    choices: list[str],
    *,
    default: str | None = None,
    help_text: str = "",
) -> PromptResult:
    """Ask the user to pick from a numbered list."""
    listing = "\n".join(f"    {i + 1}. {c}" for i, c in enumerate(choices))
    full = f"{prompt}\n{listing}"
    return ask(full, default=default, help_text=help_text, choices=choices)


def ask_yes_no(prompt: str, *, default: bool = False, help_text: str = "") -> PromptResult:
    """Ask a yes/no question."""
    return ask(
        f"{prompt} [y/N]",
        default="no" if not default else "yes",
        choices=["yes", "no"],
        help_text=help_text,
    )


def multi_ask(prompt: str, *, help_text: str = "", allow_empty: bool = True) -> list[str]:
    """Ask for a comma-separated list; 'skip' yields []."""
    result = ask(
        prompt,
        help_text=help_text + " (comma-separated)",
        validator=(lambda v: None if v else "empty list"),
    )
    if result.intent == "quit":
        raise WizardQuit()
    if result.intent == "skip" or result.intent == "back":
        return []
    return [part.strip() for part in result.value.split(",") if part.strip()]


class WizardQuit(Exception):
    """Raised when the user quits a wizard mid-way."""


def _confirm_write(path: Path) -> bool:
    if path.exists():
        resp = ask_yes_no(f"{path} already exists. Overwrite?", default=False)
        return resp.intent == "value" and str(resp.value).lower() == "yes"
    return True


def _atomic_write_or_warn(path: Path, content: str) -> bool:
    try:
        write_text_atomic(path, content, overwrite=True)
        return True
    except OCFFileExistsError as exc:
        print(f"  {exc}")
        return False


# ---------------------------------------------------------------------------
# Next-id helpers
# ---------------------------------------------------------------------------


def next_function_id(primary_domain: str) -> str:
    prefix = DOMAIN_ABBR[primary_domain]
    existing = [r for r in load_all_functions() if r.id.startswith(f"OCF-{prefix}-")]
    numbers = [int(r.id.split("-")[-1]) for r in existing] or [0]
    return f"OCF-{prefix}-{max(numbers) + 1:03d}"


def next_proposal_id() -> str:
    existing = [p.stem for p in (REPO_ROOT / "proposals").rglob("ocfp-*.md")]
    numbers = [int(p.split("-")[-1]) for p in existing] or [0]
    return f"OCFP-{max(numbers) + 1:04d}"


def next_audio_id() -> str:
    files = [p for p in AUDIO_MANIFESTS_DIR.rglob("*.yaml")] if AUDIO_MANIFESTS_DIR.is_dir() else []
    numbers = [int(p.stem.split("-")[-1]) for p in files if p.stem.startswith("OCF-AUDIO-")] or [0]
    return f"OCF-AUDIO-{max(numbers) + 1:04d}"


def next_background_id() -> str:
    base = REPO_ROOT / "audio" / "background" / "manifests"
    files = [p for p in base.rglob("*.yaml")] if base.is_dir() else []
    numbers = [int(p.stem.split("-")[-1]) for p in files if p.stem.startswith("OCF-BG-")] or [0]
    return f"OCF-BG-{max(numbers) + 1:04d}"


# ---------------------------------------------------------------------------
# Function wizard
# ---------------------------------------------------------------------------


def run_function_wizard() -> None:
    """Interactive `ocf new function` wizard."""
    print("OCF new function wizard — press ? for help, back to go back, quit to exit.\n")
    fields: dict[str, Any] = {}
    try:
        contributor = ask(
            "Contributor name (for attribution)",
            help_text="Your name as it should appear in attribution.",
        )
        if contributor.value:
            fields["contributor_name"] = contributor.value
        contact = ask(
            "Optional contact handle/email", help_text="Public handle or email; keep it optional."
        )
        if contact.value:
            fields["contributor_contact"] = contact.value

        name = ask("Function name", help_text="Human-readable name, e.g. 'Attention'.")
        if name.intent == "quit":
            return
        short_name = ask(
            "Short descriptive name",
            default=name.value,
            help_text="A one-line descriptor; defaults to the function name.",
        )
        slug = ask(
            "Slug (kebab-case)",
            default=slugify(name.value),
            help_text="URL/file-friendly identifier.",
            validator=lambda v: slugify(v) == v or "slugs must be kebab-case",
        )

        domain = ask_pick(
            "Primary domain",
            list(DOMAINS),
            default="foundation",
            help_text="The domain folder this function lives in.",
        )
        if domain.intent == "quit":
            return
        primary_domain = str(domain.value)
        secondary = multi_ask(
            "Secondary domains (optional)", help_text="Other domains this touches."
        )
        function_id = next_function_id(primary_domain)

        purpose = ask(
            "Purpose / intended behavior", help_text="What the function is for and what it does."
        )
        use_cases = multi_ask(
            "Use cases (comma-separated)", help_text="When would someone use this?"
        )
        command = ask(
            "Canonical command",
            default="PLUS-",
            help_text="Short command starting with PLUS, e.g. PLUS-FOCUS.",
            validator=lambda v: v.startswith("PLUS") or "commands must start with PLUS",
        )
        modes = multi_ask(
            "Optional command modes (comma-separated)",
            help_text="e.g. PLUS-SEE MORE / PLUS-SEE LESS.",
        )

        legacy_name = ask(
            "Legacy name (if any)", default="", help_text="Name in the legacy source system."
        )
        legacy_cmds = multi_ask("Legacy commands", help_text="Original commands, comma-separated.")
        command_status = ask_pick(
            "Command status",
            ["unchanged", "normalized", "proposed"],
            default="unchanged",
            help_text="unchanged / normalized / proposed",
        )
        rationale = None
        if command_status.value != "unchanged":
            rationale = ask(
                "Change rationale",
                help_text="Why does this command benefit from change? (required for changed commands)",
            )
        compat_state = (
            "unchanged"
            if command_status.value == "unchanged"
            else "alias-listed"
            if command_status.value == "normalized"
            else "bridge-trainable"
        )

        availability = ask_pick(
            "Source availability",
            ["available", "unavailable", "pending-source-review"],
            default="pending-source-review",
            help_text="Is original/reference training material available?",
        )
        reimpl = ask_pick(
            "OCF reimplementation status",
            ["planned", "draft", "in-progress", "complete", "released"],
            default="planned",
            help_text="planned / draft / in-progress / complete / released",
        )
        persistence = ask_pick(
            "Persistence",
            ["temporary", "permanent", "persistent", "conditional"],
            default="temporary",
        )
        activation = ask_pick(
            "Activation",
            ["manual", "automatic", "conditional", "continuous"],
            default="manual",
        )
        release_required = ask_yes_no("Requires release command?", default=False)
        release_cmd = None
        if release_required.intent == "value" and str(release_required.value).lower() == "yes":
            release_cmd = ask(
                "Release command", help_text="Command used to cancel/end the function."
            )
        friends = multi_ask(
            "Companion functions", help_text="Related function IDs, e.g. OCF-FND-002."
        )
        foes = multi_ask("Incompatible functions", help_text="Functions that clash with this one.")
        chains = multi_ask("Chains", help_text="Sequences this function can be part of.")
        safety_level = ask_pick(
            "Safety level",
            ["general", "health", "emergency", "experimental"],
            default="general",
        )
        medical = ask_yes_no("Medical relevance?", default=False)
        safety_notes = multi_ask("Safety notes", help_text="Any cautions to record.")
        evidence = ask_pick(
            "Evidence/claim state",
            [
                "source-described",
                "community-hypothesis",
                "anecdotal",
                "experimental",
                "externally-supported",
                "unverified",
            ],
            default="unverified",
        )
        source_files = multi_ask(
            "Source files (path or 'skip')", help_text="Local reference files, comma-separated."
        )
        source_urls = multi_ask("Source URLs", help_text="URLs, comma-separated.")
        sources_refs = multi_ask("References/notes", help_text="Free-form references.")
        testing_status = ask_pick(
            "Testing status",
            ["not-tested", "informal", "reported", "published"],
            default="not-tested",
        )
        audio_status = ask_pick(
            "Audio status",
            ["not-started", "draft", "review", "approved", "published"],
            default="not-started",
        )
        background_status = ask_pick(
            "Background audio status",
            ["optional", "required", "none"],
            default="optional",
        )
        notes = ask("Notes", default="", help_text="Anything else worth recording.")
    except WizardQuit:
        print("Wizard quit; nothing written.")
        return

    record = build_function_yaml(
        function_id=function_id,
        slug=str(slug.value),
        name=str(name.value),
        short_name=str(short_name.value),
        primary_domain=primary_domain,
        secondary_domains=secondary,
        purpose=str(purpose.value),
        canonical_command=str(command.value),
        modes=modes,
        legacy_name=str(legacy_name.value),
        legacy_commands=legacy_cmds,
        command_status=str(command_status.value),
        rationale=str(rationale.value) if rationale else "",
        compat_state=compat_state,
        source_availability=str(availability.value),
        reimplementation_status=str(reimpl.value),
        persistence=str(persistence.value),
        activation=str(activation.value),
        release_required=bool(
            release_required.intent == "value" and str(release_required.value).lower() == "yes"
        ),
        release_command=str(release_cmd.value) if release_cmd else None,
        companions=friends,
        incompatible=foes,
        chains=chains,
        safety_level=str(safety_level.value),
        medical_relevance=bool(medical.intent == "value" and str(medical.value).lower() == "yes"),
        safety_notes=safety_notes,
        evidence=str(evidence.value),
        applications=use_cases,
        contributor_name=fields.get("contributor_name"),
        contributor_contact=fields.get("contributor_contact"),
        source_files=source_files,
        source_urls=source_urls,
        community_notes=sources_refs,
        testing_status=str(testing_status.value),
        audio_status=str(audio_status.value),
        background_status=str(background_status.value),
        notes=str(notes.value),
    )

    target = (
        FUNCTIONS_DIR / primary_domain / f"{slug.value}.yaml"
        if slug.value
        else FUNCTIONS_DIR / primary_domain / f"{function_id.lower()}.yaml"
    )
    print("\n--- Final review ---")
    print(yaml_safe_dump(record))
    confirm = ask_yes_no("Write this file?", default=True)
    if not (confirm.intent == "value" and str(confirm.value).lower() == "yes"):
        print("Aborted; nothing written.")
        return
    if not _confirm_write(target):
        print("Overwrite declined; nothing written.")
        return
    write_text_atomic(target, yaml_safe_dump(record))
    result = validate_function_file(target)
    print_result(result)
    print("\nCreated: " + str(target.relative_to(REPO_ROOT)))
    print("Next steps:")
    print("  1. Edit the file directly or run:  ./scripts/ocf edit function " + str(slug.value))
    print("  2. Validate:                        ./scripts/ocf validate --all")
    print("  3. Regenerate indexes:              ./scripts/ocf build-index")
    print("  4. Consider a proposal:             ./scripts/ocf new proposal")


def build_function_yaml(**kwargs: Any) -> dict[str, Any]:
    """Assemble a canonical function YAML dict from wizard fields."""
    today = current_date()
    history_note = "Initial record created via wizard."
    if kwargs.get("notes"):
        history_note += f" — {kwargs['notes']}"
    secondary = [s for s in kwargs.get("secondary_domains") or [] if s in DOMAINS]
    if not secondary and not kwargs.get("secondary_domains"):
        secondary = []
    sources: list[dict[str, Any]] = []
    for s in kwargs.get("source_files") or []:
        sources.append({"type": "reference-file", "title": s, "locator": None, "url": None})
    for s in kwargs.get("source_urls") or []:
        sources.append({"type": "web", "title": s, "locator": None, "url": s})
    for s in kwargs.get("community_notes") or []:
        sources.append({"type": "community-notes", "title": s, "locator": None, "url": None})
    if not sources:
        sources.append(
            {
                "type": "pending-source-review",
                "title": "pending-source-review",
                "locator": None,
                "url": None,
            }
        )

    compat: dict[str, Any] = {"state": kwargs.get("compat_state", "unchanged")}
    if kwargs.get("rationale"):
        compat["rationale"] = kwargs["rationale"]
    if kwargs.get("legacy_commands"):
        compat["legacy_commands"] = kwargs["legacy_commands"]

    return {
        "schema_version": "1.0",
        "id": kwargs["function_id"],
        "slug": kwargs["slug"],
        "contributor": {
            "name": kwargs.get("contributor_name"),
            "contact": kwargs.get("contributor_contact"),
        },
        "canonical": {
            "name": kwargs["name"],
            "command": {
                "primary": kwargs["canonical_command"],
                "modes": kwargs.get("modes") or [],
            },
        },
        "legacy": {
            "source_system": "Monroe H-PLUS" if kwargs.get("legacy_name") else None,
            "name": kwargs.get("legacy_name") or "",
            "commands": kwargs.get("legacy_commands") or [],
            "command_status": kwargs.get("command_status", "unchanged"),
            "source_availability": kwargs.get("source_availability", "pending-source-review"),
        },
        "ocf": {
            "reimplementation_status": kwargs.get("reimplementation_status", "planned"),
            "command_review": "approved"
            if kwargs.get("command_status") == "unchanged"
            else "needs-review",
            "testing_status": kwargs.get("testing_status"),
        },
        "aliases": {
            "names": [],
            "commands": [
                c
                for c in (kwargs.get("legacy_commands") or [])
                if c != kwargs.get("canonical_command")
            ],
        },
        "classification": {
            "primary_domain": kwargs["primary_domain"],
            "secondary_domains": secondary,
        },
        "compatibility": compat,
        "status": {
            "maturity": "legacy-mapped" if kwargs.get("legacy_name") else "community-proposed",
            "implementation": "specification-only",
            "evidence": kwargs.get("evidence", "unverified"),
        },
        "lifecycle": {
            "persistence": kwargs.get("persistence", "temporary"),
            "activation": kwargs.get("activation", "manual"),
            "release": {
                "required": kwargs.get("release_required", False),
                "command": kwargs.get("release_command"),
            },
        },
        "purpose": {
            "summary": kwargs.get("purpose", "") or kwargs.get("short_name", ""),
            "source_description": None if kwargs.get("legacy_name") else None,
            "community_description": kwargs.get("short_name", ""),
        },
        "applications": kwargs.get("applications") or [],
        "use_cases": kwargs.get("applications") or [],
        "companions": kwargs.get("companions") or [],
        "incompatible_functions": kwargs.get("incompatible") or [],
        "chains": kwargs.get("chains") or [],
        "safety": {
            "level": kwargs.get("safety_level", "general"),
            "notes": kwargs.get("safety_notes") or [],
            "medical_relevance": kwargs.get("medical_relevance", False),
        },
        "claims": {
            "intended_effects": kwargs.get("intended_effects") or [],
            "prohibited_claims": ["No guaranteed effects are claimed."],
        },
        "audio": {
            "script_status": kwargs.get("audio_status", "not-started"),
            "implementation_status": "not-started",
            "background_audio": {
                "strategy": kwargs.get("background_status", "optional"),
                "engine": "farfield"
                if kwargs.get("background_status") in ("optional", "required")
                else None,
                "preset": None,
            },
        },
        "sources": sources,
        "attribution": {
            "original_authors": ["pending-source-review"] if kwargs.get("legacy_name") else [],
            "ocf_contributors": [kwargs["contributor_name"]]
            if kwargs.get("contributor_name")
            else [],
        },
        "version": {"current": "0.1.0", "created": today, "updated": today},
        "history": [{"version": "0.1.0", "date": today, "note": history_note}],
    }


# ---------------------------------------------------------------------------
# Proposal wizard
# ---------------------------------------------------------------------------


def run_proposal_wizard() -> None:
    """Interactive `ocf new proposal` wizard (produces a draft markdown)."""
    print("OCF new proposal wizard — press ? for help, quit to exit.\n")
    try:
        title = ask("Proposal title", help_text="A short descriptive title.")
        if title.intent == "quit":
            return
        authors = multi_ask("Authors (comma-separated)", help_text="Your name(s).")
        problem = ask("Problem", help_text="What problem does this address?")
        purpose = ask("Purpose", help_text="What is being proposed?")
        proposed_name = ask("Proposed name", help_text="Proposed function name.")
        proposed_command = ask(
            "Proposed command", default="PLUS-", help_text="Proposed canonical command."
        )
        length = ask("Command-length rationale", help_text="Why this length works.")
        activation = ask("Activation", default="manual")
        release = ask("Release", default="")
        persistence = ask_pick(
            "Persistence",
            ["temporary", "permanent", "persistent", "conditional"],
            default="temporary",
        )
        safety = ask("Safety", help_text="Safety considerations.")
        compatibility = ask("Compatibility", help_text="How legacy mappings are preserved.")
        evidence = ask_pick(
            "Evidence state",
            [
                "source-described",
                "community-hypothesis",
                "anecdotal",
                "experimental",
                "externally-supported",
                "unverified",
            ],
            default="community-hypothesis",
        )
        alternatives = ask("Alternatives considered", default="")
        implementation = ask("Implementation", help_text="Scripting / audio notes.")
        testing = ask("Testing plan", default="")
        sources = multi_ask("Sources (URLs/files)")
        licensing = ask("Licensing / attribution", default="Apache-2.0")
    except WizardQuit:
        print("Wizard quit; nothing written.")
        return

    proposal_id = next_proposal_id()
    body = proposal_markdown(
        proposal_id,
        str(title.value),
        authors,
        str(problem.value),
        str(purpose.value),
        str(proposed_name.value),
        str(proposed_command.value),
        str(length.value),
        str(activation.value),
        str(release.value),
        str(persistence.value),
        str(safety.value),
        str(compatibility.value),
        str(evidence.value),
        str(alternatives.value),
        str(implementation.value),
        str(testing.value),
        sources,
        str(licensing.value),
    )
    target = PROPOSALS_DIR / "draft" / f"{proposal_id.lower()}.md"
    print("\n--- Final review ---")
    print(body[:4000])
    confirm = ask_yes_no("Write this proposal?", default=True)
    if not (confirm.intent == "value" and str(confirm.value).lower() == "yes"):
        print("Aborted; nothing written.")
        return
    if not _confirm_write(target):
        print("Overwrite declined; nothing written.")
        return
    write_text_atomic(target, body)
    print("\nCreated: " + str(target.relative_to(REPO_ROOT)))
    print("Next steps: propose via pull request, then move to proposals/review/.")


def proposal_markdown(
    proposal_id: str,
    title: str,
    authors: list[str],
    problem: str,
    purpose: str,
    proposed_name: str,
    proposed_command: str,
    length: str,
    activation: str,
    release: str,
    persistence: str,
    safety: str,
    compatibility: str,
    evidence: str,
    alternatives: str,
    implementation: str,
    testing: str,
    sources: list[str],
    licensing: str,
) -> str:
    """Render a proposal document (RFC/PEP style)."""
    today = current_date()
    lines = [
        f"# {proposal_id}: {title}",
        "",
        "- Status: draft",
        f"- Date: {today}",
        f"- Authors: {', '.join(authors) or 'pending-source-review'}",
        "",
        "## Problem",
        "",
        problem or "pending-source-review",
        "",
        "## Purpose",
        "",
        purpose or "pending-source-review",
        "",
        "## Proposed name",
        "",
        proposed_name or "pending-source-review",
        "",
        "## Proposed command",
        "",
        f"`{proposed_command}`"
        if proposed_command.startswith("PLUS")
        else (proposed_command or "pending-source-review"),
        "",
        "## Command-length rationale",
        "",
        length or "pending-source-review",
        "",
        "## Activation",
        "",
        activation or "pending-source-review",
        "",
        "## Release",
        "",
        release or "None",
        "",
        "## Persistence",
        "",
        persistence,
        "",
        "## Safety",
        "",
        safety or "pending-source-review",
        "",
        "## Compatibility",
        "",
        compatibility or "Legacy commands are preserved as aliases and metadata.",
        "",
        "## Evidence state",
        "",
        evidence,
        "",
        "## Alternatives",
        "",
        alternatives or "None recorded.",
        "",
        "## Implementation",
        "",
        implementation or "pending-source-review",
        "",
        "## Testing",
        "",
        testing or "Not yet tested.",
        "",
        "## Sources",
        "",
        "- " + "\n- ".join(sources) if sources else "- pending-source-review",
        "",
        "## Licensing",
        "",
        licensing or "Apache-2.0",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Audio + background wizards
# ---------------------------------------------------------------------------


def run_audio_wizard() -> None:
    """Interactive `ocf new audio` wizard."""
    print("OCF new audio implementation wizard — press ? for help, quit to exit.\n")
    functions = load_all_functions()
    try:
        if not functions:
            print("No functions yet; create one first: ./scripts/ocf new function")
            return
        fn_choice = ask_pick(
            "Function ID",
            [f.id for f in functions],
            help_text="Which function does this implement?",
        )
        if fn_choice.intent == "quit":
            return
        function_id = str(fn_choice.value)
        title = ask("Implementation title", help_text="e.g. 'Attention basic training'.")
        author = ask("Author/contributor", default="")
        narrator = ask("Narrator", default="")
        language = ask("Language", default="en")
        license_ = ask("License", default="CC-BY-4.0")
        training_type = ask_pick(
            "Training type",
            [
                "training",
                "reinforcement",
                "quick",
                "sleep",
                "extended",
                "voice-only",
                "background-only",
                "experimental",
            ],
            default="training",
        )
        duration = ask("Duration (minutes, optional)", default="", help_text="Number.")
        transcript = ask("Transcript/script path", default="", help_text="Path to the script file.")
        induction = ask("Induction method", default="", help_text="How the session starts.")
        bg_strategy = ask_pick(
            "Background audio strategy", ["optional", "required", "none"], default="optional"
        )
        preset = ask("Background preset ID (optional)", default="", help_text="e.g. OCF-BG-0001.")
        lang = ask(
            "Canonical command rehearsal (paste text)",
            help_text="Rehearsal language for the canonical command.",
        )
        legacy_reh = ask("Legacy command rehearsal (optional)", default="")
        compat_mode = ask_pick("Compatibility mode", ["standard", "bridge"], default="standard")
        release_seq = ask("Release sequence", default="")
        safety_lang = ask(
            "Safety intro language", default="None: 'This exercise is not medical advice.'"
        )
        sample_rate = ask("Sample rate (optional)", default="")
        channels = ask("Channels (optional)", default="")
        fmt = ask("Format (optional)", default="wav")
        loudness = ask("Loudness notes (optional)", default="")
        accessibility = ask("Accessibility transcript note", default="")
        test_notes = ask("Test notes (optional)", default="")
    except WizardQuit:
        print("Wizard quit; nothing written.")
        return

    audio_id = next_audio_id()
    manifest = audio_manifest_yaml(
        audio_id,
        function_id,
        str(title.value),
        str(author.value),
        str(narrator.value),
        str(language.value),
        str(license_.value),
        str(training_type.value),
        str(duration.value),
        str(transcript.value),
        str(induction.value),
        str(bg_strategy.value),
        str(preset.value),
        str(lang.value),
        str(legacy_reh.value),
        str(compat_mode.value),
        str(release_seq.value),
        str(safety_lang.value),
        str(sample_rate.value),
        str(channels.value),
        str(fmt.value),
        str(loudness.value),
        accessibility and str(accessibility.value),
        str(test_notes.value),
    )
    target = ensure_dir(AUDIO_MANIFESTS_DIR) / f"{audio_id.lower()}.yaml"
    print("\n--- Final review ---")
    print(yaml_safe_dump(manifest))
    confirm = ask_yes_no("Write this manifest?", default=True)
    if not (confirm.intent == "value" and str(confirm.value).lower() == "yes"):
        print("Aborted; nothing written.")
        return
    if not _confirm_write(target):
        print("Overwrite declined; nothing written.")
        return
    write_text_atomic(target, yaml_safe_dump(manifest))
    validate_audio_output(target)


def audio_manifest_yaml(
    audio_id: str,
    function_id: str,
    title: str,
    author: str,
    narrator: str,
    language: str,
    license_: str,
    training_type: str,
    duration: str,
    transcript: str,
    induction: str,
    bg_strategy: str,
    preset: str,
    lang_rehearsal: str,
    legacy_rehearsal: str,
    compat_mode: str,
    release_seq: str,
    safety_lang: str,
    sample_rate: str,
    channels: str,
    fmt: str,
    loudness: str,
    accessibility: str,
    test_notes: str,
) -> dict[str, Any]:
    """Assemble an audio implementation manifest dict."""

    def opt(value: str):
        return value if value.strip() else None

    return {
        "schema_version": "1.0",
        "id": audio_id,
        "function_id": function_id,
        "title": title,
        "version": "0.1.0",
        "contributor": author or "pending-source-review",
        "narrator": opt(narrator),
        "language": language,
        "license": license_ or "pending-source-review",
        "training_type": training_type,
        "duration_minutes": float(duration)
        if duration.strip().replace(".", "", 1).isdigit()
        else None,
        "induction": induction or "pending-source-review",
        "command_rehearsal": lang_rehearsal or "pending-source-review",
        "legacy_bridge": legacy_rehearsal or None,
        "mode_rehearsal": None,
        "release_rehearsal": release_seq or None,
        "safety_intro": safety_lang,
        "transcript_path": opt(transcript),
        "background_audio": {"strategy": bg_strategy, "preset": opt(preset)},
        "technical": {
            "sample_rate": int(sample_rate) if sample_rate.strip().isdigit() else None,
            "channels": int(channels) if channels.strip().isdigit() else None,
            "format": opt(fmt),
            "loudness_notes": opt(loudness),
            "checksum_sha256": None,
        },
        "testing_notes": test_notes or None,
        "review_state": "draft",
    }


def validate_audio_output(path: Path) -> None:
    """Validate an audio manifest (prints Fluor-free result)."""
    from .validators import validate_audio_manifests

    print_result(validate_audio_manifests())
    print("\nCreated: " + str(path.relative_to(REPO_ROOT)))
    print("Next steps: ./scripts/ocf validate --all && ./scripts/ocf build-index")


def run_background_wizard() -> None:
    """Interactive `ocf new background` wizard."""
    print("OCF new background preset wizard — press ? for help, quit to exit.\n")
    try:
        name = ask("Preset name", help_text="e.g. 'Neutral focus bed'.")
        author = ask("Author", default="")
        engine = ask_pick("Engine", ["farfield", "custom", "none"], default="farfield")
        preset_file = ask(
            "Farfield preset file path (optional)", default="audio/background/presets/example.yaml"
        )
        provenance = ask_pick(
            "Provenance",
            ["original-ocf", "community", "third-party", "derived"],
            default="original-ocf",
        )
        notes = ask("Provenance notes", default="")
        intended = ask("Intended use", default="")
        functions = multi_ask(
            "Function associations (OCF IDs)", help_text="Functions this background supports."
        )
        seed = ask("Deterministic seed (integer, optional)", help_text="e.g. 12345")
        fmt = ask("Output format", default="wav")
        render_notes = ask("Render notes", default="")
        headphone = ask_yes_no("Headphone notice?", default=True)
        driving_warning = ask_yes_no("Driving warning?", default=True)
        safety_notes = multi_ask("Safety notes")
        license_ = ask("License/attribution", default="CC-BY-4.0")
    except WizardQuit:
        print("Wizard quit; nothing written.")
        return

    bg_id = next_background_id()
    manifest = background_manifest_yaml(
        bg_id,
        str(name.value),
        str(author.value),
        str(engine.value),
        str(preset_file.value),
        str(provenance.value),
        str(notes.value),
        str(intended.value),
        functions,
        seed.value,
        str(fmt.value),
        str(render_notes.value),
        headphone.intent == "value" and str(headphone.value).lower() == "yes",
        driving_warning.intent == "value" and str(driving_warning.value).lower() == "yes",
        safety_notes,
        str(license_.value),
    )
    target = ensure_dir(REPO_ROOT / "audio" / "background" / "manifests") / f"{bg_id.lower()}.yaml"
    print("\n--- Final review ---")
    print(yaml_safe_dump(manifest))
    confirm = ask_yes_no("Write this manifest?", default=True)
    if not (confirm.intent == "value" and str(confirm.value).lower() == "yes"):
        print("Aborted; nothing written.")
        return
    if not _confirm_write(target):
        print("Overwrite declined; nothing written.")
        return
    write_text_atomic(target, yaml_safe_dump(manifest))

    print_result(validate_background_manifests())
    print("\nCreated: " + str(target.relative_to(REPO_ROOT)))
    print(
        "Next steps: place a preset file under audio/background/presets/ and run "
        "./scripts/ocf audio render-background " + bg_id
    )


def background_manifest_yaml(
    bg_id: str,
    name: str,
    author: str,
    engine: str,
    preset_file: str,
    provenance: str,
    notes: str,
    intended: str,
    functions: list[str],
    seed: str,
    fmt: str,
    render_notes: str,
    headphone: bool,
    driving: bool,
    safety_notes: list[str],
    license_: str,
) -> dict[str, Any]:
    """Assemble a background-audio manifest dict."""
    return {
        "schema_version": "1.0",
        "id": bg_id,
        "name": name,
        "author": author or "pending-source-review",
        "engine": engine,
        "engine_source": {
            "repository": "https://github.com/txus/farfield" if engine == "farfield" else None,
            "version": None,
        },
        "preset": {"file": preset_file or None},
        "render": {
            "output": f"audio/background/rendered/{bg_id.lower()}.{fmt}",
            "seed": int(seed) if seed.strip().isdigit() else None,
            "deterministic": True,
        },
        "usage": {"functions": functions, "audio_implementations": []},
        "provenance": {"design": provenance, "notes": notes or None},
        "safety": {
            "headphone_notice": headphone,
            "driving_warning": driving,
            "notes": safety_notes,
        },
        "license": license_,
    }


# ---------------------------------------------------------------------------
# Test-report + source import + edit
# ---------------------------------------------------------------------------


def run_test_report_wizard() -> None:
    """Interactive `ocf new test-report` wizard."""
    print("OCF new test-report wizard — press ? for help, quit to exit.\n")
    try:
        target_id = ask(
            "Tested item (audio ID / function ID)", help_text="e.g. OCF-AUDIO-0001 or OCF-FND-002."
        )
        tester = ask("Tester name", default="")
        date = ask("Test date", default=current_date())
        context = ask("Context (environment / device)", default="")
        results = ask("Results", help_text="What did you observe?")
        issues = multi_ask("Issues found")
        verdict = ask("Overall verdict", default="informational")
    except WizardQuit:
        print("Wizard quit; nothing written.")
        return
    template = read_text(TEMPLATES_DIR / "testing-report.md")
    body = (
        template.replace("__TARGET__", str(target_id.value))
        .replace("__TESTER__", tester.value or "pending-source-review")
        .replace("__DATE__", date.value)
        .replace("__CONTEXT__", context.value or "pending-source-review")
        .replace("__RESULTS__", results.value or "pending-source-review")
        .replace("__ISSUES__", "\n".join(f"- {i}" for i in issues) or "- None recorded.")
        .replace("__VERDICT__", verdict.value or "informational")
    )
    target = (
        ensure_dir(REPO_ROOT / "audio" / "testing-reports")
        / f"{slugify(str(target_id.value))}-{slugify(date.value)}.md"
    )
    write_text_atomic(target, body)
    print("\nCreated: " + str(target.relative_to(REPO_ROOT)))
    print("Next steps: attach this report to the relevant PR or proposal.")


def run_import_source() -> None:
    """Interactive `ocf import source`: hash a local file, citation-only by default."""
    print("OCF source import — computes a SHA-256 fingerprint and offers citation-only or copy.\n")
    path_raw = ask(
        "Path to source file",
        allow_skip=False,
        help_text="Absolute or relative path (spaces are fine).",
    )
    if path_raw.intent == "quit":
        return
    path = Path(path_raw.value).expanduser()
    if not path.exists():
        print(f"error: no such file: {path}")
        return
    from .utils import sha256_of_file

    digest = sha256_of_file(path)
    size = path.stat().st_size
    print(f"  file:      {path.name}")
    print(f"  size:      {size} bytes")
    print(f"  sha256:    {digest}")

    citation_only = ask_yes_no(
        "Citation-only (default)? Copying may include copyrighted material.",
        default=True,
        help_text="Citation-only records the file reference without copying it.",
    )
    if citation_only.intent == "value" and str(citation_only.value).lower() == "yes":
        print(f"\nRecorded fingerprint; file left in place at {path}")
        print("Add a citation in the function record under 'sources' with url/locator.")
        return

    copy_target = ensure_dir(REPO_ROOT / "references" / "uploads") / path.name
    if copy_target.exists():
        overwrite = ask_yes_no(f"{copy_target} exists. Overwrite?", default=False)
        if not str(overwrite.value).lower() == "yes":
            print("Copy cancelled.")
            return
    import shutil

    shutil.copyfile(path, copy_target)
    print(f"\nCopied to {copy_target.relative_to(REPO_ROOT)}")
    print(f"sha256: {sha256_of_file(copy_target)}")
    if path.suffix.lower() in (".pdf", ".mp3", ".wav", ".flac", ".ogg"):
        print(
            "warning: you may only redistribute this file if you own rights or it is "
            "openly licensed. By default OCF does not redistribute third-party media."
        )


def run_edit_function(query: str | None) -> None:
    """Open a function record in $EDITOR for manual contribution."""
    if not query:
        print("usage: ocf edit function <slug-or-id>")
        return
    from .indexes import load_function_by_slug_or_id

    record = load_function_by_slug_or_id(query)
    if record is None:
        print(f"error: no function matches '{query}'")
        return
    import os

    editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")

    subprocess.call([editor, str(record.path)])
    result = validate_function_file(record.path)
    print_result(result)


def tmp_dump(content: str) -> Path:
    """Write content to a temp file and return its path (for editor flows)."""
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
    handle.write(content)
    handle.close()
    return Path(handle.name)
