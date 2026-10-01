"""Validation: JSON-Schema conformance plus OCF-specific rule checks.

Every function, proposal, and audio/background manifest is validated against
its JSON Schema, then rule checks are applied for command-design quality,
duplicate ids, and legacy compatibility invariants.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from .indexes import (
    discover_background_manifests,
    discover_proposal_files,
    discover_timed_transcripts,
    discover_voice_profiles,
    load_all_functions,
    load_voice_profiles,
    load_yaml_file,
)
from .locale import (
    LocaleCatalog,
    LocalizationError,
    document_key_usage,
    document_locale,
    iter_events,
    locale_direction,
    locale_language,
    message_variables,
    missing_narration_keys,
)
from .models import FunctionRecord
from .paths import schema_path

SEVERITIES = ("error", "warning", "info")

DEPRECATED_MAGNITUDE_WORDS = ("GREATER", "LESSER", "ACCELERATE")
MAX_POST_PREFIX_WORDS = 3


@dataclass
class Issue:
    """A single validation finding."""

    severity: str  # error | warning | info
    code: str
    message: str
    target: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity}")

    def format(self) -> str:
        label = self.severity.upper()
        if self.target:
            return f"[{label}] {self.code}: {self.message} ({self.target})"
        return f"[{label}] {self.code}: {self.message}"


@dataclass
class ValidationResult:
    """Aggregated validation outcome with a convenient format()."""

    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, severity: str, code: str, message: str, target: str = "") -> None:
        self.issues.append(Issue(severity, code, message, target))

    def extend(self, other: ValidationResult) -> None:
        self.issues.extend(other.issues)


def _load_schema(name: str) -> dict[str, Any]:
    path = schema_path(name)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return a list of schema error messages (empty if valid)."""
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors]


def spoken_word_count(command: str) -> int:
    """Count spoken words in a command (commas separate words; hyphens don't)."""
    text = command.replace(",", " ").replace("%", " ").strip()
    return len([w for w in text.split() if w])


def count_commands(function: FunctionRecord, legacy: bool = False) -> int:
    """Total spoken word count across canonical (or legacy) commands."""
    if legacy:
        commands = function.legacy_commands
    else:
        commands = [function.canonical_command or ""] + function.command_modes
    return sum(spoken_word_count(c) for c in commands if c)


def validate_function_schema(record: FunctionRecord) -> ValidationResult:
    """Validate one function record against function.schema.json."""
    result = ValidationResult()
    schema = _load_schema("function.schema.json")
    for message in validate_against_schema(record.data, schema):
        result.add("error", "schema", message, record.id)
    return result


def validate_command_rules(record: FunctionRecord) -> ValidationResult:
    """Command-design quality rules from docs/COMMAND_GRAMMAR.md."""
    result = ValidationResult()
    target = record.id

    # Missing PLUS prefix.
    for cmd in [record.canonical_command] + record.command_modes:
        if cmd and not cmd.strip().startswith("PLUS"):
            result.add(
                "error", "plus-prefix", f"canonical command lacks PLUS prefix: {cmd}", target
            )

    # Post-prefix word count limit.
    for cmd, count in record.spoken_words():
        if count > MAX_POST_PREFIX_WORDS:
            result.add(
                "warning",
                "too-many-words",
                f"canonical command uses {count} post-prefix spoken words "
                f"(limit {MAX_POST_PREFIX_WORDS}): {cmd}",
                target,
            )

    for cmd in record.legacy_commands:
        count = spoken_word_count(cmd)
        if count > MAX_POST_PREFIX_WORDS:
            result.add(
                "warning",
                "legacy-too-many-words",
                f"legacy command uses {count} spoken words; strong candidate for review: {cmd}",
                target,
            )

    # Deprecated magnitude vocabulary in canonical commands.
    for cmd, _ in record.spoken_words():
        for word in DEPRECATED_MAGNITUDE_WORDS:
            if word in cmd.upper().replace(",", " ").split():
                result.add(
                    "warning",
                    "deprecated-magnitude-vocab",
                    f"deprecated magnitude word '{word}' in canonical command; use MORE/LESS: {cmd}",
                    target,
                )

    # MORE/LESS pair consistency.
    cmds = [record.canonical_command or ""] + record.command_modes
    has_more = any("MORE" in c.upper().replace(",", " ").split() for c in cmds)
    has_less = any("LESS" in c.upper().replace(",", " ").split() for c in cmds)
    if has_more and not has_less:
        result.add(
            "warning",
            "asymmetric-more-less",
            f"canonical commands use MORE without a matching LESS pair: {', '.join(cmds)}",
            target,
        )
    if has_less and not has_more:
        result.add(
            "warning",
            "asymmetric-more-less",
            f"canonical commands use LESS without a matching MORE pair: {', '.join(cmds)}",
            target,
        )

    # Changed commands must carry rationale + compatibility metadata.
    if record.command_status in ("normalized", "proposed", "review-required"):
        compatibility = record.data.get("compatibility", {})
        if not compatibility:
            result.add(
                "warning",
                "no-compatibility-metadata",
                f"changed command ({record.command_status}) lacks a compatibility block",
                target,
            )
        elif not compatibility.get("rationale"):
            result.add(
                "warning",
                "no-change-rationale",
                "changed command lacks compatibility.rationale",
                target,
            )
        elif compatibility.get("state") not in (
            "alias-listed",
            "bridge-trainable",
            "canonical-first",
            "legacy-first",
        ):
            result.add(
                "warning",
                "no-compatibility-state",
                "changed command lacks a meaningful compatibility.state",
                target,
            )

    # Replacement longer than legacy.
    if record.command_status in ("normalized", "proposed", "review-required"):
        primary = record.canonical_command
        canonical_count = spoken_word_count(primary) if primary else 0
        legacy_counts = [spoken_word_count(c) for c in record.legacy_commands]
        if legacy_counts and canonical_count > max(legacy_counts) > 0:
            result.add(
                "warning",
                "replacement-longer-than-legacy",
                f"canonical command ({canonical_count} words) exceeds the legacy "
                f"command word count ({max(legacy_counts)})",
                target,
            )

    return result


def validate_collection() -> ValidationResult:
    """Cross-record rules: duplicate ids and duplicate canonical commands."""
    result = ValidationResult()
    records = load_all_functions()

    # Node's schema-per-record validation is done elsewhere; here we need ids.
    seen_ids: dict[str, FunctionRecord] = {}
    seen_commands: dict[str, list[str]] = {}
    for record in records:
        if record.id in seen_ids:
            result.add(
                "error",
                "duplicate-id",
                f"duplicate function id {record.id} in {record.path} and {seen_ids[record.id].path}",
                record.id,
            )
        else:
            seen_ids[record.id] = record

        for command in [record.canonical_command] + record.command_modes:
            if not command:
                continue
            seen_commands.setdefault(command, []).append(record.id)
        for alias in record.data.get("aliases", {}).get("commands", []):
            if record.canonical_command and alias == record.canonical_command:
                result.add(
                    "warning",
                    "alias-equals-canonical",
                    f"alias command equals canonical command: {alias}",
                    record.id,
                )

    # Canonical primary command uniqueness (modes may repeat across functions).
    primary_seen: dict[str, list[str]] = {}
    for record in records:
        primary = record.canonical_command
        if not primary:
            continue
        primary_seen.setdefault(primary, []).append(record.id)
    for command, owners in sorted(primary_seen.items()):
        if len(owners) > 1:
            result.add(
                "error",
                "duplicate-command",
                f"canonical command used by multiple functions: {command} ({', '.join(sorted(set(owners)))})",
                command,
            )

    return result


def validate_legacy_invariants() -> ValidationResult:
    """Counts and availability invariants for the initial 55-function map."""
    result = ValidationResult()
    records = load_all_functions()
    result.add("info", "legacy-count", f"loaded {len(records)} function records")

    available = [r for r in records if r.source_availability == "available"]
    unavailable = [r for r in records if r.source_availability == "unavailable"]
    result.add("info", "legacy-available", f"{len(available)} source-available functions")
    result.add("info", "legacy-unavailable", f"{len(unavailable)} source-unavailable functions")

    for record in unavailable:
        if record.reimplementation_status != "planned":
            result.add(
                "error",
                "reimplementation-target",
                f"source-unavailable function must have reimplementation_status 'planned' "
                f"(found '{record.reimplementation_status}')",
                record.id,
            )
    return result


def validate_proposals() -> ValidationResult:
    """Validate proposal files against proposal.schema.json."""
    result = ValidationResult()
    schema = _load_schema("proposal.schema.json")
    seen: dict[str, Path] = {}
    for path in discover_proposal_files():
        if path.name.lower() in ("readme.md",):
            continue
        if path.suffix.lower() == ".md":
            # Markdown proposals are prose documents and are not schema-validated.
            continue
        data = load_yaml_file(path)
        for message in validate_against_schema(data, schema):
            result.add("error", "proposal-schema", message, str(path))
        pid = data.get("id")
        if pid:
            if pid in seen:
                result.add(
                    "error", "duplicate-proposal-id", f"proposal id {pid} duplicated", str(path)
                )
            seen[pid] = path
    return result


def validate_audio_manifests() -> ValidationResult:
    """Validate audio implementation manifests."""
    result = ValidationResult()
    schema = _load_schema("audio-implementation.schema.json")
    from .indexes import discover_audio_manifests

    for path in discover_audio_manifests():
        data = load_yaml_file(path)
        for message in validate_against_schema(data, schema):
            result.add("error", "audio-schema", message, str(path))
    return result


def validate_background_manifests() -> ValidationResult:
    """Validate background-audio manifests."""
    result = ValidationResult()
    schema = _load_schema("background-audio.schema.json")
    for path in discover_background_manifests():
        data = load_yaml_file(path)
        for message in validate_against_schema(data, schema):
            result.add("error", "background-schema", message, str(path))
    return result


def validate_timed_transcript(data: dict[str, Any], path: Path) -> ValidationResult:
    """Validate one timed-transcript document (schema + timeline rules)."""
    result = ValidationResult()
    schema = _load_schema("timed-transcript.schema.json")
    for message in validate_against_schema(data, schema):
        result.add("error", "timed-schema", message, str(path))

    from .transcript import resolve_timeline

    _events, problems = resolve_timeline(data)
    for problem in problems:
        result.add("error", "timed-timeline", problem, str(path))
    result.extend(validate_narration_usage(data, path))
    return result


def validate_narration_usage(
    data: dict[str, Any], path: Path, catalog: LocaleCatalog | None = None
) -> ValidationResult:
    """Check narration keys against the locale packs.

    Catches inline listener-facing English left behind on a keyed event, keys the
    canonical pack does not define, and variable-contract mismatches.
    """
    result = ValidationResult()
    catalog = catalog or LocaleCatalog()
    usage = document_key_usage(data)
    if not usage["keyed"]:
        return result
    canonical = catalog.canonical
    commands = known_commands()
    for event in iter_events(data):
        event_id = str(event.get("id", "?"))
        key = event.get("narration_key")
        if not key:
            continue
        if event.get("text"):
            result.add(
                "warning",
                "narration-inline-text",
                f"event {event_id} carries both narration_key {key!r} and inline text; "
                "the inline wording overrides the locale pack and will not localize",
                str(path),
            )
        if canonical is not None and canonical.get(str(key)) is None:
            result.add(
                "error",
                "narration-unknown-key",
                f"event {event_id} references {key!r}, which the canonical locale "
                f"{catalog.canonical_locale} does not define",
                str(path),
            )
        for name, value in (event.get("variables") or {}).items():
            if name in ("command", "release_command") and commands and value not in commands:
                result.add(
                    "error",
                    "narration-command-invalid",
                    f"event {event_id} passes {value!r} for {name}, which is not a "
                    "canonical OCF command",
                    str(path),
                )
    locale = document_locale(data)
    try:
        catalog.spoken_chain(locale)
    except LocalizationError:
        result.add(
            "error",
            "locale-unavailable",
            f"document declares locale {locale!r} but no locale pack provides it",
            str(path),
        )
    else:
        missing = missing_narration_keys(data, locale, catalog)
        if missing:
            result.add(
                "error",
                "narration-missing-key",
                f"document needs spoken narration in {locale} that the pack does not "
                f"provide: {', '.join(missing)}",
                str(path),
            )
    return result


def validate_locale_packs(catalog: LocaleCatalog | None = None) -> ValidationResult:
    """Validate every locale pack: schema, contracts, coverage, and provenance."""
    result = ValidationResult()
    catalog = catalog or LocaleCatalog()
    for problem in catalog.problems:
        result.add("error", "locale-pack-malformed", problem)
    if not catalog.locales():
        result.add("warning", "locale-pack-none", f"no locale packs found in {catalog.root}")
        return result

    manifest_schema = _load_schema("locale-manifest.schema.json")
    resource_schema = _load_schema("locale-resource.schema.json")
    canonical = catalog.canonical
    commands = known_commands()

    for locale in catalog.locales():
        pack = catalog.require(locale)
        target = str(pack.path) if pack.path else f"locales/{locale}"
        for message in validate_against_schema(pack.manifest, manifest_schema):
            result.add("error", "locale-manifest-schema", message, target)
        if pack.manifest.get("status") != "canonical":
            translation = pack.translation
            if not translation.get("source_locale"):
                result.add(
                    "error",
                    "locale-provenance-missing",
                    f"{locale} is not canonical but declares no translation.source_locale",
                    target,
                )
            if translation.get("source_locale") == locale:
                result.add(
                    "error",
                    "locale-provenance-self",
                    f"{locale} records itself as its own translation source",
                    target,
                )
        for resource in pack.manifest.get("resources") or []:
            filename = str(resource.get("file", ""))
            data = load_yaml_file(Path(pack.path) / filename) if pack.path else {}
            for message in validate_against_schema(data, resource_schema):
                result.add("error", "locale-resource-schema", message, f"{target}/{filename}")

        for key, entry in pack.entries.items():
            where = f"{target}/{entry.file or '?'}#{key}"
            for problem in entry.check_contract():
                result.add("error", "locale-variable-contract", f"{key}: {problem}", where)
            try:
                message_variables(entry.text)
            except LocalizationError as exc:
                result.add("error", "locale-message-syntax", f"{key}: {exc}", where)
            if canonical is not None and canonical.locale == locale:
                continue
            source = canonical.get(key) if canonical else None
            if source is not None:
                missing_variables = sorted(set(source.variables) - set(entry.variables))
                extra_variables = sorted(set(entry.variables) - set(source.variables))
                if missing_variables or extra_variables:
                    detail = []
                    if missing_variables:
                        detail.append(f"missing {', '.join(missing_variables)}")
                    if extra_variables:
                        detail.append(f"extra {', '.join(extra_variables)}")
                    result.add(
                        "error",
                        "locale-variable-mismatch",
                        f"{key}: declares different template variables than "
                        f"{canonical.locale} ({'; '.join(detail)})",
                        where,
                    )
            declared_commands = [
                name for name in ("command", "release_command") if name in entry.variables
            ]
            for token in re.findall(r"\bPLUS-[A-Z-]+\b", entry.text):
                if token not in commands:
                    result.add(
                        "error",
                        "locale-command-invalid",
                        f"{key}: references command {token!r}, which is not a canonical "
                        "OCF command (see legacy/hplus-command-map.json)",
                        where,
                    )
            if declared_commands:
                result.add(
                    "info",
                    "locale-command-placeholder",
                    f"{key}: takes a command value; documents that reference it are "
                    "checked against the canonical command list",
                    where,
                )
            for token in entry.pronunciation:
                if token not in entry.text and not entry.variables:
                    result.add(
                        "warning",
                        "locale-pronunciation-unused",
                        f"{key}: pronunciation hint for {token!r}, which the message "
                        "neither contains nor can receive as a variable",
                        where,
                    )

        if not pack.is_canonical and canonical is not None:
            missing_keys = catalog.missing_keys(locale)
            if missing_keys:
                shown = ", ".join(missing_keys[:8])
                if len(missing_keys) > 8:
                    shown += f", +{len(missing_keys) - 8} more"
                result.add(
                    "warning",
                    "locale-partial",
                    f"{locale} is missing {len(missing_keys)} canonical key(s): {shown}",
                    target,
                )
            unknown = catalog.unknown_keys(locale)
            if unknown:
                result.add(
                    "error",
                    "locale-unknown-keys",
                    f"{locale} defines keys the canonical pack does not: "
                    f"{', '.join(unknown)}",
                    target,
                )
            if catalog.stale_translations(locale):
                result.add(
                    "warning",
                    "locale-stale",
                    f"{locale} was translated from "
                    f"{pack.translation.get('source_locale')}@"
                    f"{pack.translation.get('source_semantic_version')}; canonical is now "
                    f"{canonical.semantic_version} (retranslate or re-verify)",
                    target,
                )
            for key in catalog.stale_keys(locale):
                result.add(
                    "info",
                    "locale-entry-stale",
                    f"{key}: canonical entry version is newer than the translation's",
                    target,
                )
        if pack.direction != locale_direction(locale):
            result.add(
                "warning",
                "locale-direction",
                f"{locale} declares direction {pack.direction!r} but "
                f"{locale_direction(locale)} is expected for {locale_language(locale)}",
                target,
            )
    result.add(
        "info",
        "locale-count",
        f"validated {len(catalog.locales())} locale pack(s): "
        f"{', '.join(catalog.locales())}",
    )
    return result


def known_commands() -> set[str]:
    """Canonical OCF commands, for validating command references in resources."""
    commands: set[str] = set()
    for record in load_all_functions():
        command = record.canonical_command
        if command:
            commands.add(str(command))
        for mode in record.command_modes:
            if mode:
                commands.add(str(mode))
    return commands



def validate_timed_transcript_file(path: Path) -> ValidationResult:
    """Validate a single timed-transcript YAML file."""
    return validate_timed_transcript(load_yaml_file(path), path)


def validate_timed_transcripts() -> ValidationResult:
    """Validate every OCF timed-transcript document under audio/scripts/."""
    result = ValidationResult()
    paths = discover_timed_transcripts()
    result.add("info", "timed-count", f"validated {len(paths)} timed-transcript document(s)")
    for path in paths:
        result.extend(validate_timed_transcript_file(path))
    return result


def validate_voice_profiles() -> ValidationResult:
    """Validate voice profiles against voice-profile.schema.json."""
    result = ValidationResult()
    schema = _load_schema("voice-profile.schema.json")
    seen: dict[str, Path] = {}
    paths = discover_voice_profiles()
    result.add("info", "voice-count", f"validated {len(paths)} voice profile(s)")
    for path in paths:
        data = load_yaml_file(path)
        for message in validate_against_schema(data, schema):
            result.add("error", "voice-schema", message, str(path))
        pid = data.get("id")
        if pid in seen:
            result.add(
                "error", "duplicate-voice-id", f"voice profile id {pid} duplicated", str(path)
            )
        seen[pid if pid is not None else path.name] = path
        slug = data.get("slug")
        if slug and any(
            p.get("slug") == slug and p.get("id") != pid for p in load_voice_profiles()
        ):
            result.add(
                "error",
                "duplicate-voice-slug",
                f"voice profile slug {slug!r} duplicated",
                str(path),
            )
    return result


def validate_all() -> ValidationResult:
    """Run every validation pass over the repository."""
    result = ValidationResult()
    for record in load_all_functions():
        result.extend(validate_function_schema(record))
        result.extend(validate_command_rules(record))
    result.extend(validate_collection())
    result.extend(validate_legacy_invariants())
    result.extend(validate_proposals())
    result.extend(validate_audio_manifests())
    result.extend(validate_background_manifests())
    result.extend(validate_timed_transcripts())
    result.extend(validate_voice_profiles())
    result.extend(validate_locale_packs())
    return result


def validate_function_file(path: Path) -> ValidationResult:
    """Validate a single function YAML file."""
    result = ValidationResult()
    data = load_yaml_file(path)
    record = FunctionRecord(
        id=str(data.get("id", "")),
        slug=str(data.get("slug", "")),
        path=path,
        data=data,
    )
    result.extend(validate_function_schema(record))
    result.extend(validate_command_rules(record))
    return result


def print_result(result: ValidationResult) -> int:
    """Print a validation result; return process exit code."""
    for issue in sorted(result.issues, key=lambda i: (i.severity != "error", i.target, i.message)):
        print(issue.format())
    print(
        f"--- {len(result.errors)} errors, {len(result.warnings)} warnings, "
        f"{len(result.issues)} total findings"
    )
    return 0 if result.ok else 1
