"""Explicit twelve-decision successor with checked historical projections."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import yaml

from .paths import REPO_ROOT
from .utils import OCFError

ID = "OCF-COMMAND-SIMPLIFICATION-001"
SOURCE = "8ec5b0395c7a5c05fa629d64297d3bf048b097f9"
LEDGER = "function-content/editorial/command-simplification-001.json"
LEDGER_SHA256 = "4122593d490fca71490f561d130899317029070459fb93bac56842fe6d63aaa3"
BASELINE = "tests/fixtures/hplus-narration-text-baseline-008.json"
PREVIOUS_BASELINE = "tests/fixtures/hplus-narration-text-baseline-007.json"
PREVIOUS_LOCK = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-010.json"
PAIRS = {
    "OCF-BOD-002": ("Circulation", "PLUS-CIRCULATE", "Plus Flow Smooth", "Plus Circulate"),
    "OCF-BOD-005": (
        "Appetite Choice",
        "PLUS-SATISFIED",
        "Plus Satisfied Supplied",
        "Plus Satisfied",
    ),
    "OCF-BOD-006": ("Heart Flow", "PLUS-HEART-FLOW", "Plus Heart Better", "Plus Heart Flow"),
    "OCF-BOD-013": ("Body Tune-Up", "PLUS-TUNE-UP", "Plus Balance Heal", "Plus Tune Up"),
    "OCF-EMG-001": (
        "Injury Response",
        "PLUS-INJURY-RESPONSE",
        "Plus Control Balance Restore",
        "Plus Injury Response",
    ),
    "OCF-EMG-002": (
        "Toxic Exposure Response",
        "PLUS-TOXIC-CLEAR",
        "Plus Clear Remove",
        "Plus Toxic Clear",
    ),
    "OCF-FND-002": ("Focus", "PLUS-FOCUS", "Plus Focus", "Plus Focus"),
    "OCF-PRF-003": ("Coordination", "PLUS-COORDINATE", "Plus Smooth Fast", "Plus Coordinate"),
}
ARTWORK = {
    "OCF-EXP-001": "Align your intention with the reality you choose",
    "OCF-EXP-003": "Release unwanted beliefs and recurring patterns",
    "OCF-EXP-006": "Strengthen intuitive awareness and understanding",
    "OCF-EXP-005": "Set an intention to discourage unwanted insects",
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approved_function(before):
    """Change presentation only; every procedure and lifecycle byte is retained."""
    result = deepcopy(before)
    owner = before["id"]
    title, display, old_spoken, spoken = PAIRS[owner]
    primary = next(row for row in result["commands"] if row.get("designation") == "primary")
    if primary["spoken"] != old_spoken:
        raise OCFError("simplification predecessor cue differs from approval: " + owner)
    previous = {
        "former-title": before["canonical"]["name"],
        "former-primary": before["canonical"]["command"]["primary"],
        "former-teaching": old_spoken,
    }
    result["canonical"]["name"] = title
    result["canonical"]["command"]["primary"] = display
    primary["spoken"] = spoken
    primary["spoken_review"] = "reviewed"
    if old_spoken != spoken and "observed_phrase" in primary:
        primary["observed_phrase"]["text"] = spoken
        primary["observed_phrase"]["relationship"] = "canonical-match"
    for kind in ("display", "spoken"):
        primary["localization"][kind + "_cue_key"] = (
            "commands." + primary["id"].lower() + "." + kind + "-cue"
        )
    for kind, current in (
        ("former-title", title),
        ("former-primary", display),
        ("former-teaching", spoken),
    ):
        if previous[kind] != current:
            row = {"text": previous[kind], "kind": kind, "decision": ID}
            if kind != "former-title":
                row["command_id"] = primary["id"]
            result.setdefault("historical_lookup", []).append(row)
    result["compatibility"] = {
        "state": "historical-lookup",
        "rationale": "Approved presentation successor "
        + ID
        + "; superseded wording remains historical lookup.",
    }
    return result


def record(root=REPO_ROOT):
    path = root / LEDGER
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    if sha(raw) != LEDGER_SHA256:
        raise OCFError("immutable command simplification ledger drift")
    data = json.loads(raw)
    if (
        data["id"] != ID
        or data["source_commit"] != SOURCE
        or data["confirmation"] != "Confirm implementation"
    ):
        raise OCFError("command simplification authorization drift")
    return data


def predecessor(root, name, text):
    data = record(root)
    row = data["files"].get(name) if data else None
    if row is None:
        return text
    if sha(text) != row["after_sha256"] or sha(row["before"]) != row["before_sha256"]:
        raise OCFError("command simplification source drift: " + name)
    return row["before"]


def before_texts(root, texts):
    result = dict(texts)
    data = record(root)
    for identity, row in data["speech"].items() if data else []:
        if result.get(identity) != row["after"]:
            raise OCFError("command simplification resolved speech drift: " + identity)
        result[identity] = row["before"]
    return result


def verify(root=REPO_ROOT):
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    data = record(root)
    if data is None:
        return ["command simplification successor missing"]
    for name in data["files"]:
        predecessor(root, name, (root / name).read_text(encoding="utf-8"))
    for name, checksum in data["immutable_files"].items():
        if sha((root / name).read_text(encoding="utf-8")) != checksum:
            raise OCFError("command simplification immutable predecessor drift: " + name)
    texts = narration_texts(root)
    if text_fingerprints(before_texts(root, texts)) != json.loads(
        (root / PREVIOUS_BASELINE).read_text(encoding="utf-8")
    ):
        raise OCFError("command simplification changed unrelated protected speech")
    if text_fingerprints(texts) != json.loads((root / BASELINE).read_text(encoding="utf-8")):
        raise OCFError("command simplification baseline drift")
    expected_scope = set()
    for owner, (_, _, old, new) in PAIRS.items():
        roles = ("closer",) if old == new else ("function-body", "closer")
        for role in roles:
            identity = f"locales/en-US/hplus-{owner}.yaml::hplus.function.{owner.lower()}.{role}"
            expected_scope.add(identity)
            row = data["speech"][identity]
            before, after = (
                (old, new)
                if old != new
                else (
                    "This concludes your OCF Attention exercise.",
                    "This concludes your OCF Focus exercise.",
                )
            )
            if before not in row["before"] or row["after"] != row["before"].replace(before, after):
                raise OCFError("unapproved command simplification speech: " + identity)
            for side in ("before", "after"):
                if sha(row[side]) != row[side + "_sha256"]:
                    raise OCFError("command simplification speech hash drift")
    if set(data["speech"]) != expected_scope:
        raise OCFError("command simplification speech scope drift")
    for name in data["function_files"]:
        old = yaml.safe_load(data["files"][name]["before"])
        if yaml.safe_load((root / name).read_text(encoding="utf-8")) != approved_function(old):
            raise OCFError("command simplification changed behavior: " + name)
    ui = yaml.safe_load((root / "locales/en-US/ui.yaml").read_text(encoding="utf-8"))["entries"]
    for owner, text in ARTWORK.items():
        entry = ui[f"functions.{owner.lower()}.artwork-description"]
        if entry["text"] != text or entry["status"] != "reviewed":
            raise OCFError("artwork differs from explicit approval: " + owner)
    old_lock = json.loads((root / PREVIOUS_LOCK).read_text(encoding="utf-8"))
    new_lock = json.loads((root / data["lock"]).read_text(encoding="utf-8"))
    expected = deepcopy(old_lock)
    expected.update(id=new_lock["id"], version=new_lock["version"])
    for name in expected["files"]:
        if name in data["files"]:
            if not name.startswith("locales/en-US/hplus-"):
                raise OCFError("unapproved engineering dependency change")
            expected["files"][name] = data["files"][name]["after_sha256"]
    if new_lock != expected:
        raise OCFError("command simplification changed engineering defaults")
    return []
