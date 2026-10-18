"""Immutable, explicitly confirmed metadata-only successor and predecessor view."""

import hashlib
import json

import yaml

from .paths import REPO_ROOT
from .utils import OCFError

RECORD = "function-content/editorial/functional-metadata-001.json"
ID = "OCF-FUNCTIONAL-METADATA-001"
AUTHORIZATION = "09603d115243e85912884425ca845200fa02195d8ca2761dc12c1075373d1e59"


def check_record(data):
    digest = hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    if data.get("id") != ID or digest != AUTHORIZATION:
        raise OCFError("functional metadata differs from the confirmed decision set")


def record(root=REPO_ROOT):
    data = json.loads((root / RECORD).read_text(encoding="utf-8"))
    check_record(data)
    return data


def predecessor_file(root, name):
    from .cue_migration import contained

    current = contained(root, name).read_text(encoding="utf-8")
    data = record(root)
    if name not in data["source_files"]:
        return current
    if hashlib.sha256(current.encode()).hexdigest() != data["source_files"][name]["after_sha256"]:
        raise OCFError("functional metadata source drift: " + name)
    previous = data["predecessor_files"][name]
    if hashlib.sha256(previous.encode()).hexdigest() != data["source_files"][name]["before_sha256"]:
        raise OCFError("functional metadata predecessor drift: " + name)
    return previous


def verify(data, root, read, texts):
    from .cue_migration import contained

    check_record(data)

    def sha(value):
        return hashlib.sha256(value.encode()).hexdigest()

    problems = []
    for name, checks in data["source_files"].items():
        if sha(read(name)) != checks["after_sha256"]:
            problems.append("functional metadata source drift: " + name)
        if sha(data["predecessor_files"][name]) != checks["before_sha256"]:
            problems.append("functional metadata predecessor drift: " + name)
    for name, change in data["function_changes"].items():
        if yaml.safe_load(read(name)) != change["after"]:
            problems.append("unapproved functional change: " + name)
        if yaml.safe_load(data["predecessor_files"][name]) != change["before"]:
            problems.append("unapproved functional predecessor: " + name)
    for name, checksum in data["unchanged_files"].items():
        path = contained(root, name)
        actual = (
            sha(read(name))
            if path.suffix in {".yaml", ".json", ".txt"}
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        if actual != checksum:
            problems.append("metadata-only migration changed protected dependency: " + name)
    current = {key: sha(text) for key, text in texts.items()}
    if current != data["resolved_baseline"]:
        problems.append("metadata-only migration changed resolved narration")
    if (
        json.loads(contained(root, data["integrity_baseline"]).read_text(encoding="utf-8"))
        != data["resolved_baseline"]
    ):
        problems.append("metadata-only migration changed the existing narration baseline")
    return problems
