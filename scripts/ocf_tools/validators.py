"""Validation: JSON-Schema conformance plus OCF-specific rule checks.

Every function, proposal, and audio/background manifest is validated against
its JSON Schema, then rule checks are applied for command-design quality,
duplicate ids, and legacy compatibility invariants.
"""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from referencing import Registry, Resource

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
    validator = Draft7Validator(schema, registry=_schema_registry())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors]


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    """Resolve shared schema definitions locally, never by network."""
    resources = []
    for path in schema_path("timed-transcript.schema.json").parent.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


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

    # Exclude negated MORE/LESS (e.g., "NO MORE", "NOT MORE", "PLUS-NO MORE") from detection
    def has_meaningful_more(cmd: str) -> bool:
        words = cmd.upper().replace(",", " ").split()
        for i, word in enumerate(words):
            if word == "MORE":
                # Check if preceded by negation words or prefixes
                if i > 0:
                    prev = words[i - 1]
                    if (
                        prev in ("NO", "NOT", "NEVER")
                        or prev.endswith("-NO")
                        or prev.endswith("_NO")
                    ):
                        continue
                return True
        return False

    def has_meaningful_less(cmd: str) -> bool:
        words = cmd.upper().replace(",", " ").split()
        for i, word in enumerate(words):
            if word == "LESS":
                if i > 0:
                    prev = words[i - 1]
                    if (
                        prev in ("NO", "NOT", "NEVER")
                        or prev.endswith("-NO")
                        or prev.endswith("_NO")
                    ):
                        continue
                return True
        return False

    has_more = any(has_meaningful_more(c) for c in cmds)
    has_less = any(has_meaningful_less(c) for c in cmds)
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


def validate_command_metadata(records: list[FunctionRecord]) -> ValidationResult:
    """Validate structured command references without requiring migrated records."""
    from .commands import (
        CommandMetadataError,
        load_procedure_catalog,
        resolve_procedure,
        validate_command_records,
    )
    from .locale import NARRATION_DOMAIN, LocaleCatalog

    result = ValidationResult()
    try:
        procedures = load_procedure_catalog()
    except (CommandMetadataError, OSError) as exc:
        result.add(
            "error",
            "command-procedure-catalog",
            str(exc),
            "function-content/command-procedures.yaml",
        )
        procedures = {}

    locale_catalog = LocaleCatalog()
    canonical_locale = locale_catalog.canonical

    def has_narration_key(key: str) -> bool:
        entry = canonical_locale.get(key) if canonical_locale else None
        return entry is not None and entry.domain == NARRATION_DOMAIN

    def narration_contains_phrase(phrase: str, key: str) -> bool:
        entry = canonical_locale.get(key) if canonical_locale else None
        if entry is None or entry.domain != NARRATION_DOMAIN:
            return False
        phrase_words = re.findall(r"[A-Z0-9]+", phrase.upper())
        spoken_words = re.findall(r"[A-Z0-9]+", entry.text.upper())
        width = len(phrase_words)
        return bool(phrase_words) and any(
            spoken_words[index : index + width] == phrase_words
            for index in range(len(spoken_words) - width + 1)
        )

    for procedure in procedures.values():
        for key in procedure.get("source_narration_keys", []):
            if not has_narration_key(key):
                result.add(
                    "error",
                    "command-procedure-evidence",
                    f"procedure {procedure['id']} references unavailable narration key {key!r}",
                    procedure["id"],
                )

    seen_ids: dict[str, str] = {}
    for record in records:
        for message in validate_command_records(record):
            result.add("error", "command-metadata", message, record.id)
        special_phrases = {
            phrase.get("id"): phrase
            for phrase in record.data.get("command_phrases", [])
            if isinstance(phrase, dict)
        }
        for command in record.command_records:
            if command.id in seen_ids:
                result.add(
                    "error",
                    "duplicate-command-id",
                    f"command ID {command.id} is used by {seen_ids[command.id]} and {record.id}",
                    command.id,
                )
            else:
                seen_ids[command.id] = record.id
            try:
                resolve_procedure(command, procedures)
            except CommandMetadataError as exc:
                result.add("error", "command-procedure-reference", str(exc), command.id)
            procedure = command.procedure
            if procedure:
                for key in procedure.get("evidence_keys", []):
                    if not has_narration_key(key):
                        result.add(
                            "error",
                            "command-procedure-evidence",
                            f"command {command.id} references unavailable narration key {key!r}",
                            command.id,
                        )
            observed = command.observed_phrase
            if observed:
                key = observed.get("narration_key", "")
                if not has_narration_key(key):
                    result.add(
                        "error",
                        "command-observed-phrase-evidence",
                        f"command {command.id} references unavailable narration key {key!r}",
                        command.id,
                    )
                elif not narration_contains_phrase(observed.get("text", ""), key):
                    result.add(
                        "error",
                        "command-observed-phrase-mismatch",
                        f"command {command.id} observed phrase is absent from narration {key!r}",
                        command.id,
                    )
        for phrase in special_phrases.values():
            key = phrase.get("source_narration_key", "")
            if not has_narration_key(key):
                result.add(
                    "error",
                    "special-command-phrase-evidence",
                    f"special command phrase {phrase.get('id')} references unavailable narration key {key!r}",
                    record.id,
                )
            elif not narration_contains_phrase(phrase.get("phrase", ""), key):
                result.add(
                    "error",
                    "special-command-phrase-mismatch",
                    f"special command phrase {phrase.get('id')} is absent from narration {key!r}",
                    record.id,
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
    schema_failed = bool(result.errors)

    from .transcript import resolve_timeline

    try:
        _events, problems = resolve_timeline(data)
        for problem in problems:
            result.add("error", "timed-timeline", problem, str(path))
        result.extend(validate_narration_usage(data, path))
        result.extend(validate_narration_hygiene(data, path, LocaleCatalog()))
    except (AttributeError, KeyError, TypeError, ValueError, LocalizationError):
        # Shape errors already reported by the schema must remain diagnostics,
        # not crashes. Still collect runtime findings when invalid data is usable;
        # never conceal an interpreter defect for schema-valid input.
        if not schema_failed:
            raise
    return result


def _event_variables(event: dict, result: ValidationResult, path: Path) -> dict:
    values = event.get("variables", {})
    if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
        result.add(
            "error",
            "narration-variables",
            f"event {event.get('id')}: variables must be a string-keyed object",
            str(path),
        )
        return {}
    return values


def validate_narration_usage(
    data: dict[str, Any], path: Path, catalog: LocaleCatalog | None = None
) -> ValidationResult:
    """Check narration keys against the locale packs.

    Catches inline listener-facing English left behind on a keyed event, keys the
    canonical pack does not define, and variable-contract mismatches.
    """
    result = ValidationResult()
    result.extend(validate_command_ownership(data, path))
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
        for name, value in _event_variables(event, result, path).items():
            if (
                name in ("command", "release_command")
                and commands
                and (not isinstance(value, str) or value not in commands)
            ):
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


def validate_command_ownership(data: dict[str, Any], path: Path) -> ValidationResult:
    """Commands used by keyed explanations belong to an identified function."""
    result = ValidationResult()
    records = {record.id: record for record in load_all_functions()}
    vocabulary = sorted(known_commands(), key=len, reverse=True)
    catalog = None
    for event in iter_events(data):
        variables = _event_variables(event, result, path)
        commands = {
            name: variables[name] for name in ("command", "release_command") if name in variables
        }
        text = event.get("text", "")
        text = text if isinstance(text, str) else ""
        if event.get("narration_key") and not text:
            catalog = catalog or LocaleCatalog()
            entry = catalog.canonical.get(event["narration_key"]) if catalog.canonical else None
            text = entry.text if entry else ""
        if (
            data.get("function_id")
            or event.get("function_id")
            or event.get("narration_key")
            or str(event.get("semantic", "")).startswith("function.command.")
        ):
            remaining = text
            for index, command in enumerate(vocabulary):
                if re.search(r"(?<![A-Z0-9-])" + re.escape(command) + r"(?![A-Z0-9-])", remaining):
                    commands[f"literal-{index}"] = command
                    remaining = remaining.replace(command, "")
        if not commands:
            continue
        owner = event.get("function_id") or data.get("function_id")
        record = records.get(owner) if isinstance(owner, str) else None
        if record is None:
            result.add(
                "error",
                "narration-command-owner",
                f"event {event.get('id')}: command owner requires a known function_id, got {owner!r}",
                str(path),
            )
            continue
        for name, command in commands.items():
            is_release = (
                name == "release_command"
                or event.get("narration_key") == "function.release.command"
            )
            if is_release:
                allowed = [(record.data.get("lifecycle", {}).get("release") or {}).get("command")]
            else:
                allowed = [record.canonical_command] + record.command_modes
            if command not in allowed:
                result.add(
                    "error",
                    "narration-command-owner",
                    f"event {event.get('id')}: command {command!r} does not belong to owner {owner}",
                    str(path),
                )
    return result


def validate_narration_hygiene(
    data: dict[str, Any], path: Path = Path("session"), catalog: LocaleCatalog | None = None
) -> ValidationResult:
    """Structural mistakes only; intentional repetition is supported."""
    from .semantics import operational_cue_error

    result = ValidationResult()
    seen_narration = set()
    seen_cues = set()
    semantics = {
        event["semantic"] for event in iter_events(data) if isinstance(event.get("semantic"), str)
    }
    origins = {
        entry.get("id"): entry.get("locale")
        for entry in (data.get("narration") or {}).get("resolved", [])
    }
    for event in iter_events(data):
        event_id = event.get("id")
        cue_problem = operational_cue_error(event)
        if cue_problem:
            result.add("error", "semantic-cue-operation", cue_problem, str(path))
        text = event.get("text")
        key = event.get("narration_key")
        if event.get("narration_required") and not (
            key or (isinstance(text, str) and text.strip())
        ):
            result.add(
                "error",
                "narration-required",
                f"event {event_id}: missing required narration",
                str(path),
            )
        if "text" in event and not key and (not isinstance(text, str) or not text.strip()):
            result.add("error", "narration-empty", f"event {event_id}: empty narration", str(path))
        if isinstance(text, str):
            if re.search(r"\{[a-z][a-z0-9_]*(?:[,}])", text):
                result.add(
                    "error",
                    "narration-variable",
                    f"event {event_id}: unresolved template variables",
                    str(path),
                )
            if re.search(r"\b(?:TODO|TBD|TRANSLATE-ME|pending-source-review)\b", text, re.I):
                result.add(
                    "error",
                    "narration-placeholder",
                    f"event {event_id}: untranslated placeholder",
                    str(path),
                )
            if re.search(r"\[(?:pause|silence)\b", text, re.I):
                result.add(
                    "error",
                    "narration-pause",
                    f"event {event_id}: pause directives belong in timing.pause_after",
                    str(path),
                )
        timing = event.get("timing", {})
        if not isinstance(timing, dict):
            result.add(
                "error",
                "narration-timing",
                f"event {event_id}: timing must be an object",
                str(path),
            )
            continue
        for name in ("preferred_duration", "maximum_duration"):
            value = timing.get(name)
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value <= 0
            ):
                result.add(
                    "error", "narration-timing", f"event {event_id}: malformed {name}", str(path)
                )
        pause = timing.get("pause_after", 0)
        if (
            not isinstance(pause, (int, float))
            or isinstance(pause, bool)
            or not math.isfinite(pause)
            or pause < 0
        ):
            result.add(
                "error", "narration-pause", f"event {event_id}: malformed pause_after", str(path)
            )
        if timing.get("anchor", "start") != "start" and "after" not in event:
            result.add(
                "error",
                "semantic-anchor",
                f"event {event_id}: end anchor requires an after reference",
                str(path),
            )
        for field_name in ("semantic", "auditory_cue"):
            if field_name in event and not re.fullmatch(
                r"[a-z][a-z0-9-]*(\.[a-z0-9-]+)+", str(event[field_name])
            ):
                result.add(
                    "error",
                    "semantic-identity",
                    f"event {event_id}: invalid {field_name} identity",
                    str(path),
                )
        variables = _event_variables(event, result, path)
        if "after" in event and (not isinstance(event["after"], str) or not event["after"]):
            result.add(
                "error",
                "semantic-anchor",
                f"event {event_id}: after must be a nonempty event ID",
                str(path),
            )
        if (
            "at" in event
            and event["at"] is not None
            and not isinstance(event["at"], (str, int, float))
        ):
            result.add(
                "error",
                "semantic-anchor",
                f"event {event_id}: at must be a timestamp or seconds",
                str(path),
            )
        anchor = tuple(
            repr(value)
            for value in (
                event.get("at"),
                event.get("after"),
                event.get("offset", 0),
                timing.get("anchor", "start"),
            )
        )
        narration = (str(key or text), repr(sorted(variables.items())), anchor)
        cue = (repr(event.get("auditory_cue")), anchor)
        if not event.get("intentional_repeat"):
            if (key or text) and narration in seen_narration:
                result.add(
                    "error",
                    "narration-duplicate",
                    f"event {event_id}: duplicate narration at the same anchor",
                    str(path),
                )
            if event.get("auditory_cue") and cue in seen_cues:
                result.add(
                    "error",
                    "semantic-cue-duplicate",
                    f"event {event_id}: duplicate auditory cue at the same anchor",
                    str(path),
                )
        if key or text:
            seen_narration.add(narration)
        if event.get("auditory_cue"):
            seen_cues.add(cue)
        if key and catalog:
            try:
                entry, _ = catalog.resource(
                    key,
                    origins.get(event_id) or document_locale(data),
                    domain="narration",
                    fallback=False,
                )
                for reference in entry.requires_events:
                    if reference not in semantics:
                        result.add(
                            "error",
                            "narration-event-reference",
                            f"event {event_id}: narration requires absent semantic event {reference}",
                            str(path),
                        )
            except LocalizationError as exc:
                result.add("error", "narration-resource", str(exc), str(path))
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
            if not entry.text.strip():
                result.add("error", "locale-empty", f"{key}: empty narration/resource", where)
            if entry.domain == "narration" and re.search(
                r"\b(?:TODO|TBD|TRANSLATE-ME|pending-source-review)\b", entry.text, re.I
            ):
                result.add("error", "locale-placeholder", f"{key}: untranslated placeholder", where)
            try:
                for problem in entry.check_contract():
                    result.add("error", "locale-variable-contract", f"{key}: {problem}", where)
                message_variables(entry.text)
            except LocalizationError as exc:
                result.add("error", "locale-message-syntax", f"{key}: {exc}", where)
            if canonical is not None and canonical.locale == locale:
                continue
            source = canonical.get(key) if canonical else None
            if source is not None:
                if set(source.requires_events) != set(entry.requires_events):
                    result.add(
                        "error",
                        "locale-event-contract",
                        f"{key}: translation changed required semantic events",
                        where,
                    )
                if set(source.required_pronunciation) != set(entry.required_pronunciation):
                    result.add(
                        "error",
                        "locale-pronunciation-contract",
                        f"{key}: translation changed required pronunciation tokens",
                        where,
                    )
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
            remaining = entry.text
            for command in sorted(commands, key=len, reverse=True):
                remaining = re.sub(
                    r"(?<![A-Z0-9-])" + re.escape(command) + r"(?![A-Z0-9-])", "", remaining
                )
            # Use the same boundaries as canonical matching. Every remaining
            # standalone PLUS token is unknown; known complete commands were
            # removed above without changing the resource itself.
            for token in re.findall(r"(?<![A-Z0-9-])PLUS-[A-Z-]+(?![A-Z0-9-])", remaining):
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
                    f"{locale} defines keys the canonical pack does not: {', '.join(unknown)}",
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
        f"validated {len(catalog.locales())} locale pack(s): {', '.join(catalog.locales())}",
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
        release = (record.data.get("lifecycle", {}).get("release") or {}).get("command")
        if release:
            commands.add(str(release))
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
    from .utils import OCFError

    result = ValidationResult()
    records = load_all_functions()
    for record in records:
        result.extend(validate_function_schema(record))
        result.extend(validate_command_rules(record))
    result.extend(validate_command_metadata(records))
    result.extend(validate_collection())
    result.extend(validate_legacy_invariants())
    result.extend(validate_proposals())
    result.extend(validate_audio_manifests())
    result.extend(validate_background_manifests())
    result.extend(validate_timed_transcripts())
    result.extend(validate_voice_profiles())
    result.extend(validate_locale_packs())
    result.extend(validate_session_library())
    result.extend(validate_semantic_dsp_profiles())
    from .content import validate_library

    for error in validate_library():
        result.add("error", "function-content", error)
    from .voice_registry import load_registry

    try:
        load_registry()
    except OCFError as exc:
        result.add("error", "voice-registry", str(exc))
    return result


def validate_semantic_dsp_profiles() -> ValidationResult:
    from .audio_build import _resolve_background_manifest
    from .semantic_dsp import PROFILES_DIR, load_profile
    from .utils import OCFError

    result = ValidationResult()
    for path in PROFILES_DIR.glob("*.yaml"):
        try:
            profile = load_profile(path)
            if profile["initial_state"] not in profile["states"]:
                raise OCFError("initial state must be configured or explicitly disabled")
            for state, choice in profile["states"].items():
                if choice["mode"] == "preset" and not _resolve_background_manifest(
                    choice["preset"]
                ):
                    raise OCFError(f"state {state}: unknown background {choice['preset']}")
        except OCFError as exc:
            result.add("error", "semantic-dsp-profile", str(exc), str(path))
    return result


def validate_session_library() -> ValidationResult:
    """Validate stage/cue records and compose library templates structurally.

    Explicit architecture drafts report pending narration without claiming to
    be listener-ready. Runtime preflight still rejects their missing resources.
    """
    from .semantics import (
        CUE_PROFILES_DIR,
        STAGES_DIR,
        bind_document_cues,
        load_cue_profile,
        load_stage,
    )
    from .session import TEMPLATES_DIR, compose, load_template
    from .transcript import resolve_timeline
    from .utils import OCFError

    result = ValidationResult()
    for path in STAGES_DIR.glob("*.yaml"):
        try:
            load_stage(str(path))
        except OCFError as exc:
            result.add("error", "stage-invalid", str(exc), str(path))
    for path in CUE_PROFILES_DIR.glob("*.yaml"):
        try:
            load_cue_profile(str(path))
        except OCFError as exc:
            result.add("error", "cue-profile-invalid", str(exc), str(path))
    for path in TEMPLATES_DIR.glob("*.yaml"):
        try:
            template = load_template(str(path))
            # Validate reusable bridge content without inventing contributor
            # slot wording or trying to schedule an empty reinforcement slot.
            structural_template = deepcopy(template)
            structural_template["slots"] = {"required": [], "optional": []}
            for section in structural_template["sections"]:
                if section.get("pace") == "block" and (
                    section.get("slot") or section.get("from_slot")
                ):
                    # Validate the semantic/relative placement contract without
                    # fabricating or copying contributor wording into this
                    # structural-only pass.
                    semantic = section.get("semantic") or "authoring.unassigned"
                    section["lines"] = [
                        {
                            "id": f"structural-slot-marker-{section['id']}",
                            "semantic": semantic,
                            "narration_required": False,
                        }
                    ]
                    section.setdefault("type", "custom")
                    section.setdefault("start", 0.0)
                    section.pop("after", None)
                for field_name in ("slot", "from_slot", "repeat", "pace"):
                    section.pop(field_name, None)
                for field_name in (
                    "pacing_key",
                    "repeat_pacing_key",
                    "repeat_gap_pacing_key",
                    "pause_after_pacing_key",
                    "gain_db_pacing_key",
                    "pause_before_s",
                    "after_anchor",
                ):
                    section.pop(field_name, None)
            doc = compose(structural_template, {}, title=template["name"])
            _, problems = resolve_timeline(doc)
            for problem in problems:
                result.add("error", "template-timeline", problem, str(path))
            bind_document_cues(doc)
            if template.get("content_status") == "architecture-draft":
                structural = validate_narration_hygiene(doc, path)
                for issue in structural.issues:
                    if issue.code != "narration-required":
                        result.issues.append(issue)
                result.add(
                    "info",
                    "template-narration-pending",
                    "architecture draft: required original narration is not authored; not render-ready",
                    str(path),
                )
            else:
                result.extend(validate_narration_usage(doc, path))
                result.extend(validate_narration_hygiene(doc, path, LocaleCatalog()))
        except OCFError as exc:
            result.add("error", "template-invalid", str(exc), str(path))
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
    result.extend(validate_command_metadata([record]))
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
