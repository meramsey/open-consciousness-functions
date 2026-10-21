"""Explicit four-candidate approval with checked historical predecessor views."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import yaml

from .paths import REPO_ROOT
from .utils import OCFError

LEDGER = "function-content/editorial/approved-candidates-001.json"
LEDGER_SHA256 = "2b3418b311119d1b5a02fd48ba829081b716c2c9b979f02effbeedab311512d7"
BASELINE = "tests/fixtures/hplus-narration-text-baseline-007.json"
SOURCE = "911dbd0f24618091e34e8a816275ab7eabbf97bb"
MANIFEST = "locales/en-US/hplus-OCF-EXP-001.yaml"
APPROVED = {
    "manifest-v2": ("OCF-EXP-001", "functions/experimental/mobius-west.yaml", MANIFEST),
    "dissolve": (
        "OCF-EXP-003",
        "functions/experimental/dissolve.yaml",
        "locales/en-US/original-OCF-EXP-003.yaml",
    ),
    "intuition": (
        "OCF-EXP-006",
        "functions/experimental/intuition.yaml",
        "locales/en-US/original-OCF-EXP-006.yaml",
    ),
    "clear-zone": (
        "OCF-EXP-005",
        "functions/experimental/clear-zone.yaml",
        "locales/en-US/original-OCF-EXP-005.yaml",
    ),
}
SNAPSHOTS = {
    "manifest-v2": "6dc76e9827512efc1c2f4f532366def13480b68bf4d6793e8f7ca13f4903e608",
    "dissolve": "929f81f7d6fc3f6d44f5d3c00e1890c86765c1b7e0ce06bab75a6dbde953c471",
    "intuition": "7f5d38d589943fbac4ca6fe7212ee25ab27d4416ec5141455bab386f0a3cc147",
    "clear-zone": "f2bd428f97719b926f1c8bab5d9c8c11546ad65f0c025f6cbb7f2f74f5a79e80",
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(root=REPO_ROOT):
    path = root / LEDGER
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    if sha(raw) != LEDGER_SHA256:
        raise OCFError("immutable candidate approval ledger drift")
    data = json.loads(raw)
    if (
        data["source_commit"] != SOURCE
        or data["confirmation"] != "Confirm implementation"
        or set(data["approvals"]) != set(APPROVED)
    ):
        raise OCFError("candidate approval scope drift")
    for name, row in data["approvals"].items():
        if (
            row["function_id"] != APPROVED[name][0]
            or row["user_response"] != "1"
            or row["snapshot_sha256"] != SNAPSHOTS[name]
        ):
            raise OCFError("candidate approval differs from the user's decision")
    return data


def predecessor(root, name, text):
    from .command_simplification import predecessor as before_simplification

    text = before_simplification(root, name, text)
    data = record(root)
    row = data["files"].get(name) if data else None
    if row is None:
        return text
    if sha(text) != row["after_sha256"]:
        raise OCFError("approved candidate source drift: " + name)
    if row["before"] is None:
        return text
    if sha(row["before"]) != row["before_sha256"]:
        raise OCFError("approved candidate predecessor drift: " + name)
    return row["before"]


def before_texts(root, texts):
    from .command_simplification import before_texts as before_simplification

    texts = before_simplification(root, texts)
    data = record(root)
    result = dict(texts)
    for identity, row in data["speech"].items() if data else []:
        if result.get(identity) != row["after"]:
            raise OCFError("approved candidate resolved speech drift: " + identity)
        result[identity] = row["before"]
    return result


def approved_function(before):
    """Only editorial statuses change; existing purpose, modes and procedure stay."""
    result = deepcopy(before)
    result["audio"]["script_status"] = "approved"
    result["status"]["implementation"] = "script-approved"
    result["ocf"]["command_review"] = "approved"
    result["ocf"]["reimplementation_status"] = "in-progress"
    for command in result["commands"]:
        command["spoken_review"] = "reviewed"
        if result["id"] == "OCF-EXP-006":
            command["procedure"]["status"] = "documented"
    return result


def verify(root=REPO_ROOT):
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    from .locale import LocaleCatalog

    data = record(root)
    if data is None:
        return ["candidate approval ledger missing"]
    for name, row in data["files"].items():
        predecessor(root, name, (root / name).read_text(encoding="utf-8"))
    for name, checksum in data["immutable_files"].items():
        from .command_simplification import predecessor as before_simplification_file

        current = before_simplification_file(root, name, (root / name).read_text(encoding="utf-8"))
        if sha(current) != checksum:
            raise OCFError("immutable approval predecessor changed: " + name)
    from .command_simplification import before_texts as before_simplification

    texts = before_simplification(root, narration_texts(root))
    previous = json.loads((root / data["previous_baseline"]).read_text(encoding="utf-8"))
    if text_fingerprints(before_texts(root, narration_texts(root))) != previous:
        raise OCFError("candidate approval changed unrelated protected narration")
    if text_fingerprints(texts) != json.loads((root / BASELINE).read_text(encoding="utf-8")):
        raise OCFError("candidate approval baseline drift")
    expected_speech = {
        f"{MANIFEST}::hplus.function.ocf-exp-001.{role}"
        for role in ("opener", "function-body", "closer")
    }
    if set(data["speech"]) != expected_speech:
        raise OCFError("candidate approval protected speech scope drift")
    catalog = LocaleCatalog(root / "locales")
    for name, (_, function, resource) in APPROVED.items():
        snapshot_path = root / f"function-content/editorial/candidates/{name}.en-US.yaml"
        raw = snapshot_path.read_text(encoding="utf-8")
        if sha(raw) != SNAPSHOTS[name]:
            raise OCFError("approved candidate snapshot changed: " + name)
        snapshot = yaml.safe_load(raw)
        live = yaml.safe_load((root / resource).read_text(encoding="utf-8"))
        expected = deepcopy(snapshot)
        for key, entry in expected["entries"].items():
            entry["status"] = "reviewed"
            resolved = catalog.resource(key, "en-US", domain="narration", fallback=False)[0]
            if sha(resolved.text) != data["approvals"][name]["resolved_sha256"][key]:
                raise OCFError("approved candidate speech differs from presented wording: " + key)
        if live != expected:
            raise OCFError("candidate promotion changed authored wording or provenance: " + name)
        if name == "manifest-v2":
            continue
        old = data["files"][function]["before"]
        if name == "intuition":
            old = (
                root / "function-content/editorial/candidates/intuition.function.yaml"
            ).read_text(encoding="utf-8")
        expected_function = approved_function(yaml.safe_load(old))
        if name == "intuition":
            expected_function["documentation"] = data["intuition_documentation"]
            expected_function["commands"][0]["localization"] = data["intuition_localization"]
        if yaml.safe_load((root / function).read_text(encoding="utf-8")) != expected_function:
            raise OCFError("candidate approval changed function behavior: " + name)
    old_lock = json.loads((root / data["previous_lock"]).read_text(encoding="utf-8"))
    new_lock = json.loads((root / data["lock"]).read_text(encoding="utf-8"))
    expected_lock = deepcopy(old_lock)
    expected_lock.update(id=new_lock["id"], version=new_lock["version"])
    expected_lock["files"][MANIFEST] = data["files"][MANIFEST]["after_sha256"]
    if new_lock != expected_lock:
        raise OCFError("candidate approval changed engineering defaults")
    return []
