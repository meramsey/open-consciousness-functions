"""Approved documentation-only successor; immutable earlier reviews stay verifiable."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from .paths import REPO_ROOT
from .utils import OCFError, yaml_safe_load

LEDGER = "function-content/editorial/guide-review-001.json"
LEDGER_SHA256 = "33335cbf4c2d83ae68870f32d7560aec167995d29ff81ed486886cfcddccae61"
EDGES = {
    "OCF-EXP-001": ["OCF-EXP-003", "OCF-EXP-006"],
    "OCF-EXP-003": ["OCF-EXP-006"],
    "OCF-BOD-006": ["OCF-BOD-002"],
    "OCF-SLP-005": ["OCF-SLP-001"],
    "OCF-FND-002": ["OCF-COG-007"],
}
IMPRINT_PURPOSE = (
    "Consciously capture and retain selected information or experiences, "
    "with Plus Recall for deliberate retrieval."
)
STEP_TEXT = {
    "select-question-or-situation": "Bring one question or situation into awareness.",
    "think-or-say-in-mind": "Think or say the selected command in the mind.",
    "allow-quiet-moment": "Allow a quiet moment to notice what arises.",
    "consider-and-choose-response": "Consider its meaning and choose a response with care and discernment.",
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def revised_purpose(owner, text):
    if owner == "OCF-COG-004":
        return IMPRINT_PURPOSE
    text = text.replace("proposed concise cue", "activation cue")
    if owner == "OCF-PRF-004":
        text = text.replace("PLUS-LIGHT.", "PLUS-LIGHT STEP.")
    if owner == "OCF-SLP-001":
        text = text.replace("PLUS-RESTORE.", "PLUS-RESTORATIVE SLEEP.")
    return text


def check_function_scope(before, after):
    """Only approved companion links, description cleanup and step labels may differ."""
    expected = deepcopy(before)
    owner = expected["id"]
    if owner in EDGES:
        expected["companions"] = EDGES[owner]
    for field in ("summary", "community_description"):
        expected["purpose"][field] = revised_purpose(owner, expected["purpose"][field])
    if owner == "OCF-EXP-006":
        for step in expected["commands"][0]["procedure"]["override_steps"]:
            step["localization_key"] = f"functions.ocf-exp-006.procedure.{step['id']}"
    if expected != after:
        raise OCFError("guide review exceeds approved metadata-only scope: " + owner)


def record(root=REPO_ROOT):
    path = root / LEDGER
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if sha(text) != LEDGER_SHA256:
        raise OCFError("immutable guide review approval drift")
    data = json.loads(text)
    if data["confirmation"] != "Yes" or len(data["decisions"]) != 6:
        raise OCFError("guide review requires six decisions and final confirmation")
    actual = {}
    for row in data["decisions"]:
        if row["response"] != "1" or row["dependency"] != "optional":
            raise OCFError("guide relationship approval drift")
        actual.setdefault(row["source_id"], []).append(row["related_id"])
    if actual != EDGES:
        raise OCFError("guide review relationship scope drift")
    return data


def predecessor(root, name, text):
    data = record(root)
    row = data["files"].get(name) if data else None
    if row is None:
        return text
    if sha(text) != row["after_sha256"] or sha(row["before"]) != row["before_sha256"]:
        raise OCFError("guide review source fingerprint drift: " + name)
    if name.startswith("functions/"):
        check_function_scope(yaml_safe_load(row["before"]), yaml_safe_load(text))
    return row["before"]


def verify(root=REPO_ROOT):
    data = record(root)
    if data:
        for name in data["files"]:
            if not (
                name.startswith("functions/")
                or name in {"locales/en-US/commands.yaml", "locales/en-US/ui.yaml"}
            ):
                raise OCFError("guide review file outside metadata-only scope")
            predecessor(root, name, (root / name).read_text(encoding="utf-8"))
    return []


def relationships(owner, *, root=REPO_ROOT):
    """Only explicitly approved directional edges present in canonical YAML are exposed."""
    data = record(root)
    rows = [r for r in data["decisions"] if r["source_id"] == owner.id] if data else []
    if owner.data.get("companions", []) != [r["related_id"] for r in rows]:
        raise OCFError("companion metadata lacks matching guide approval: " + owner.id)
    return rows
