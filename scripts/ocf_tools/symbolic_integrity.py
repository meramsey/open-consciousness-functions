"""Immutable structural migration checks: raw templates and resolved bytes differ."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .paths import REPO_ROOT
from .utils import OCFError

RECORD = "function-content/editorial/symbolic-cues-001.json"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ledger(root=REPO_ROOT):
    path = root / RECORD
    if not path.is_file():
        return None
    from .validators import _load_schema, validate_against_schema

    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_against_schema(data, _load_schema("symbolic-cue-migration.schema.json"))
    if errors:
        raise OCFError("invalid symbolic migration: " + " | ".join(errors))
    return data


def predecessor_text(root, name):
    """Old approval remains checkable against exact retained predecessor bytes."""
    data = ledger(root)
    from .editorial_successors import before_file

    current = before_file(root, name)
    if data and name in data["predecessor_files"]:
        row = data["files"][name]
        text = data["predecessor_files"][name]
        if sha(text) != row["before_sha256"] or sha(current) != row["after_sha256"]:
            raise OCFError("structural predecessor/current file fingerprint mismatch: " + name)
        return text
    return current


def verify(root=REPO_ROOT):
    from tools.check_hplus_narration_integrity import narration_texts

    from .editorial_successors import before_file, before_texts
    from .locale import LocaleCatalog

    data = ledger(root)
    if data is None:
        raise OCFError("symbolic migration record missing")
    problems = []
    for name, checks in data["files"].items():
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
            raise OCFError("symbolic migration path escapes repository")
        if sha(before_file(root, name)) != checks["after_sha256"]:
            problems.append("symbolic raw source drift: " + name)
        if sha(data["predecessor_files"][name]) != checks["before_sha256"]:
            problems.append("symbolic predecessor tampered: " + name)
    catalog = LocaleCatalog(root / "locales")
    texts = before_texts(root, narration_texts(root))
    if {key: sha(text) for key, text in texts.items()} != data["resolved_baseline"]:
        problems.append("resolved protected narration differs from byte-identical predecessor")
    for row in data["entries"]:
        raw = yaml.safe_load(before_file(root, row["path"]))["entries"][row["key"]]["text"]
        expected = row["before_text"]
        for span in reversed(row["spans"]):
            if (
                expected[span["start"] : span["end"]] != span["before"]
                or span["symbol"] != "cue.primary"
            ):
                raise OCFError("symbolic replacement span mismatch")
            expected = expected[: span["start"]] + "{{ cue.primary }}" + expected[span["end"] :]
        if expected != raw or sha(raw) != row["template_sha256"]:
            problems.append("nonstructural template change: " + row["key"])
        resolved = texts[row["path"] + "::" + row["key"]]
        if resolved.encode("utf-8") != row["before_text"].encode("utf-8"):
            problems.append("resolved byte drift: " + row["key"])
    owners = {owner.id: owner for owner in catalog.function_records()}
    for identifier, binding in data["narration_bindings"].items():
        if identifier not in owners or owners[identifier].data.get("narration") != binding:
            problems.append("function narration binding drift: " + identifier)
    old_path = root / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"
    old_raw = old_path.read_text(encoding="utf-8")
    old = json.loads(old_raw)
    new = json.loads(
        (root / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-003.json").read_text(encoding="utf-8")
    )
    if (
        sha(old_raw) != data["predecessor_lock_sha256"]
        or old["profiles"] != new["profiles"]
        or old["files"].keys() != new["files"].keys()
    ):
        problems.append("immutable predecessor or engineering lock identity changed")
    allowed = {row["path"] for row in data["entries"]}
    if any(
        new["files"][name] != checksum
        for name, checksum in old["files"].items()
        if name not in allowed
    ):
        problems.append("non-editorial engineering hash changed")
    return problems
