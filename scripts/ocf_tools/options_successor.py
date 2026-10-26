"""Approved Options speech successor, outside the frozen structural ledgers."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import yaml

from .paths import REPO_ROOT
from .utils import OCFError

LEDGER = "function-content/editorial/options-001.json"
LEDGER_SHA256 = "524280ba65b7e507ab4e693e696570d70611163743d7e0b8cfb84e6dcb9a569b"
OWNER = "OCF-COG-005"
FUNCTION = "functions/cognition/options.yaml"
NARRATION = "locales/en-US/hplus-OCF-COG-005.yaml"
OLD = "Plus Options Choices"
NEW = "Plus Options"
BASELINE = "tests/fixtures/hplus-narration-text-baseline-006.json"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(root=REPO_ROOT):
    path = root / LEDGER
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    if sha(raw) != LEDGER_SHA256:
        raise OCFError("Options immutable successor ledger drift")
    data = json.loads(raw)
    if data["approval"] != {
        "function_id": OWNER,
        "display": "PLUS-OPTIONS",
        "before": OLD,
        "after": NEW,
    }:
        raise OCFError("Options successor differs from explicit approval")
    expected = {
        f"{NARRATION}::hplus.function.ocf-cog-005.{role}": count
        for role, count in (("function-body", 2), ("closer", 1))
    }
    if set(data["speech"]) != set(expected):
        raise OCFError("Options successor speech scope changed")
    for identity, count in expected.items():
        row = data["speech"][identity]
        if row["before"].count(OLD) != count or row["after"] != row["before"].replace(OLD, NEW):
            raise OCFError("Options successor contains unapproved speech")
        for side in ("before", "after"):
            if sha(row[side]) != row[side + "_sha256"]:
                raise OCFError("Options successor speech fingerprint drift")
    return data


def predecessor(root, name, text):
    from .candidate_approval import predecessor as before_candidates

    text = before_candidates(root, name, text)
    data = record(root)
    row = data["files"].get(name) if data else None
    if row is None:
        return text
    if sha(text) != row["after_sha256"] or sha(row["before"]) != row["before_sha256"]:
        raise OCFError("Options successor source drift: " + name)
    return row["before"]


def before_texts(root, texts):
    from .candidate_approval import before_texts as before_candidates

    texts = before_candidates(root, texts)
    data = record(root)
    result = dict(texts)
    for identity, row in data["speech"].items() if data else []:
        if result.get(identity) != row["after"]:
            raise OCFError("Options successor resolved speech drift: " + identity)
        result[identity] = row["before"]
    return result


def approved_function(before):
    after = deepcopy(before)
    primary, historical = after["commands"]
    primary["spoken"] = NEW
    primary["spoken_review"] = "reviewed"
    primary["observed_phrase"]["text"] = NEW
    primary["observed_phrase"]["relationship"] = "canonical-match"
    for kind in ("display", "spoken"):
        primary["localization"][kind + "_cue_key"] = (
            "commands.ocf-cmd-cog-005-primary." + kind + "-cue"
        )
    historical["availability"] = "historical-lookup"
    historical["documentation"]["visible"] = False
    after["aliases"]["commands"] = []
    after["aliases"]["command_ids"] = []
    after["compatibility"] = {
        "state": "historical-lookup",
        "rationale": "Plus Options Choices is historical vocabulary; the approved active cue is Plus Options.",
    }
    after["historical_lookup"] = [
        {
            "text": OLD,
            "kind": "former-teaching",
            "command_id": historical["id"],
            "decision": "OCF-OPTIONS-001",
        }
    ]
    return after


def verify(root=REPO_ROOT):
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    data = record(root)
    if data is None:
        return ["Options successor missing"]
    for name in data["files"]:
        predecessor(root, name, (root / name).read_text(encoding="utf-8"))
    previous = json.loads((root / data["previous_baseline"]).read_text(encoding="utf-8"))
    if (
        sha((root / data["previous_baseline"]).read_text(encoding="utf-8"))
        != data["previous_baseline_sha256"]
    ):
        raise OCFError("Options immutable predecessor baseline drift")
    texts = narration_texts(root)
    if text_fingerprints(before_texts(root, texts)) != previous:
        raise OCFError("Options changed unrelated protected speech")
    from .candidate_approval import before_texts as before_candidates

    if text_fingerprints(before_candidates(root, texts)) != json.loads(
        (root / BASELINE).read_text(encoding="utf-8")
    ):
        raise OCFError("Options successor baseline drift")
    old = yaml.safe_load(data["files"][FUNCTION]["before"])
    if approved_function(old) != yaml.safe_load((root / FUNCTION).read_text(encoding="utf-8")):
        raise OCFError("Options changed function behavior or stable identities")
    old = yaml.safe_load(data["files"][NARRATION]["before"])
    new = yaml.safe_load((root / NARRATION).read_text(encoding="utf-8"))
    for identity, row in data["speech"].items():
        key = identity.split("::")[1]
        entry = new["entries"][key]
        if (
            entry["text"] != row["before"].replace(OLD, "{{ cue.primary }}")
            or sha(entry["text"]) != row["raw_template_sha256"]
        ):
            raise OCFError("Options raw template drift")
        if entry["cue_template"] != {"function_id": OWNER, "allowed": ["cue.primary"]}:
            raise OCFError("Options cue binding drift")
        for field in ("text", "version", "cue_template"):
            if field in old["entries"][key]:
                entry[field] = old["entries"][key][field]
            else:
                entry.pop(field, None)
    if new != old:
        raise OCFError("Options changed unrelated narration metadata")
    old_lock = json.loads((root / data["previous_lock"]).read_text(encoding="utf-8"))
    new_lock = json.loads((root / data["lock"]).read_text(encoding="utf-8"))
    expected = deepcopy(old_lock)
    expected.update(id=new_lock["id"], version=new_lock["version"])
    expected["files"][NARRATION] = data["files"][NARRATION]["after_sha256"]
    if new_lock != expected:
        raise OCFError("Options changed engineering configuration")
    return []
