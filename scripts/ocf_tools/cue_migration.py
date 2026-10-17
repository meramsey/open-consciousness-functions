"""Verify the explicit editorial successor without blessing arbitrary text drift."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath

from .paths import REPO_ROOT
from .utils import OCFError

RECORD = Path("function-content/editorial/approved-title-cues-001.json")


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def decision_record(root: Path = REPO_ROOT):
    return json.loads((root / RECORD).read_text(encoding="utf-8"))


def contained(root, name):
    path = Path(name)
    resolved = (root / path).resolve()
    if (
        path.is_absolute()
        or PureWindowsPath(name).drive
        or ".." in path.parts
        or not resolved.is_relative_to(root.resolve())
    ):
        raise OCFError("editorial dependency escapes checkout: " + name)
    return resolved


def replay_change(row):
    text = row["before_text"]
    if text_sha(text) != row["before_sha256"]:
        raise OCFError("editorial predecessor text fingerprint mismatch")
    for substitution in row["substitutions"]:
        old, new = substitution["before"], substitution["after"]
        if not old or text.count(old) != substitution["count"]:
            raise OCFError("editorial substitution occurrence count mismatch")
        text = text.replace(old, new)
    if text_sha(text) != row["after_sha256"]:
        raise OCFError("editorial successor text fingerprint mismatch")
    return text


def verify_migration(root: Path = REPO_ROOT):
    from tools.approved_cue_migration import APPROVED, text_operations
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    data = decision_record(root)
    from .validators import _load_schema, validate_against_schema

    schema_errors = validate_against_schema(
        data, _load_schema("editorial-cue-migration.schema.json")
    )
    if schema_errors:
        raise OCFError("invalid editorial migration: " + " | ".join(schema_errors))
    if {row["function_id"] for row in data["decisions"]} != set(APPROVED):
        raise OCFError("editorial decision owners differ from the explicit approved allowlist")
    previous_path = contained(root, data["previous_integrity_baseline"])
    previous_raw = previous_path.read_text(encoding="utf-8")
    if text_sha(previous_raw) != data["previous_baseline_sha256"]:
        return ["immutable predecessor narration baseline changed"]
    previous = json.loads(previous_raw)
    if not isinstance(previous, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in previous.items()
    ):
        raise OCFError("invalid predecessor narration fixture")
    for identity in previous:
        contained(root, identity.split("::", 1)[0])
    current = text_fingerprints(narration_texts(root))
    problems = []
    permitted = {row["identity"]: row for row in data["allowed_text_changes"]}
    if len(permitted) != len(data["allowed_text_changes"]):
        raise OCFError("duplicate protected identity in editorial allowlist")
    for row in permitted.values():
        if row["function_id"] not in APPROVED or not row["identity"].startswith(
            f"locales/en-US/hplus-{row['function_id']}.yaml::"
        ):
            raise OCFError("protected entry is outside the approved function scope")
    if set(current) != set(previous):
        problems.append("editorial migration changed protected resource identities")
    actual_texts = narration_texts(root)
    for identity in previous.keys() & current.keys():
        row = permitted.get(identity)
        if row is None:
            if current[identity] != previous[identity]:
                problems.append("unapproved narration change: " + identity)
        else:
            expected_text = replay_change(row)
            # An edited manifest cannot bless arbitrary mechanisms or procedures:
            # the English migration's exact title/cue operations remain required.
            text_operations(row["before_text"], expected_text)
            if (
                row["before_sha256"] != previous[identity]
                or expected_text != actual_texts[identity]
            ):
                problems.append("approved narration delta mismatch: " + identity)
    if permitted.keys() - previous.keys():
        problems.append("editorial allowlist contains unknown protected identities")
    for name, expected in data["unaffected_function_sha256"].items():
        if text_sha(contained(root, name).read_text(encoding="utf-8")) != expected:
            problems.append("unaffected function changed: " + name)
    for name, values in data["source_files"].items():
        if text_sha(contained(root, name).read_text(encoding="utf-8")) != values["after_sha256"]:
            problems.append("editorial source fingerprint mismatch: " + name)
    # Frozen configuration is retained; the successor only changes declared content.
    old_lock_raw = contained(root, data["previous_defaults_lock"]).read_text(encoding="utf-8")
    if text_sha(old_lock_raw) != data["previous_defaults_sha256"]:
        problems.append("immutable predecessor defaults lock changed")
        return problems
    old_lock = json.loads(old_lock_raw)
    new_lock = json.loads(contained(root, data["defaults_lock"]).read_text(encoding="utf-8"))
    if not all(
        isinstance(lock, dict)
        and isinstance(lock.get("profiles"), dict)
        and isinstance(lock.get("files"), dict)
        for lock in (old_lock, new_lock)
    ):
        raise OCFError("invalid defaults manifest structure in editorial migration")
    if (
        old_lock["profiles"] != new_lock["profiles"]
        or old_lock["files"].keys() != new_lock["files"].keys()
    ):
        problems.append("successor defaults engineering identity/dependency membership changed")
    changed_files = {row["narration_file"] for row in data["decisions"]}
    for name, checksum in old_lock["files"].items():
        if name not in changed_files and new_lock["files"].get(name) != checksum:
            problems.append("non-editorial engineering dependency changed: " + name)
    return problems
