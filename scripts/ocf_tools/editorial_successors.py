"""Explicit approved successors preserve earlier integrity revisions without rebaselining.

Historical verifiers receive a checked predecessor view. Current sources and
resolved text are always verified before they can be projected backward.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import yaml

from .paths import REPO_ROOT
from .utils import OCFError

REGISTERED = (
    "function-content/editorial/approved-title-cues-002.json",
    "function-content/editorial/approved-title-cues-003.json",
)
APPROVED = {
    "OCF-EDITORIAL-TITLE-CUES-002": ("OCF-BOD-003", "Comfort", "PLUS-COMFORT", "Plus Comfort"),
    "OCF-EDITORIAL-TITLE-CUES-003": (
        "OCF-BOD-014",
        "Regenerate",
        "PLUS-REGENERATE",
        "Plus Regenerate",
    ),
}
APPROVED_PREDECESSORS = {
    "OCF-EDITORIAL-TITLE-CUES-002": {
        "title": "De-Discomfort",
        "display_cue": "PLUS-COMFORT",
        "spoken_cue": "Plus Five Five Five One Five",
    },
    "OCF-EDITORIAL-TITLE-CUES-003": {
        "title": "Regenerate",
        "display_cue": "PLUS-REGENERATE",
        "spoken_cue": "Plus Build Live",
    },
}


def function_scope(before, after, decision):
    """Only the approved identity/presentation edits may differ in function YAML."""
    old, new = deepcopy(before), deepcopy(after)
    owner = decision["function_id"]
    if (
        new.get("id") != owner
        or new.get("canonical", {}).get("name") != decision["current_title"]
        or new.get("canonical", {}).get("command", {}).get("primary") != decision["display_cue"]
    ):
        raise OCFError("function YAML does not implement the approved pair")
    old["canonical"]["name"] = new["canonical"]["name"]
    old["canonical"]["command"]["primary"] = new["canonical"]["command"]["primary"]
    primary = decision["primary_command_id"]
    retired = set(decision["historical_command_ids"])
    if len(old["commands"]) != len(new["commands"]):
        raise OCFError("stable command identity count changed")
    for left, right in zip(old["commands"], new["commands"], strict=True):
        if left["id"] != right["id"]:
            raise OCFError("stable command identities or ordering changed")
        if right["id"] == primary:
            if (
                right.get("spoken") != decision["spoken_cue"]
                or right.get("spoken_review") != "reviewed"
            ):
                raise OCFError("authoritative spoken cue differs from approval")
            if right.get("observed_phrase") != {
                "text": decision["spoken_cue"],
                "narration_key": f"hplus.function.{owner.lower()}.function-body",
                "relationship": "canonical-match",
            }:
                raise OCFError("observed teaching must match the approved primary cue")
            for key in ("spoken", "spoken_review", "observed_phrase"):
                left[key] = deepcopy(right[key])
            for key in ("display_cue_key", "spoken_cue_key"):
                expected_key = (
                    "commands."
                    + primary.lower()
                    + (".display-cue" if key == "display_cue_key" else ".spoken-cue")
                )
                if right["localization"].get(key) != expected_key:
                    raise OCFError("approved cue binding must retain its stable command identity")
                left.setdefault("localization", {})[key] = right["localization"][key]
        elif right["id"] in retired:
            if (
                left["role"] != "legacy-alias"
                or right.get("availability") != "historical-lookup"
                or right.get("documentation", {}).get("visible") is not False
            ):
                raise OCFError("only superseded primary aliases may become historical-only")
            left["availability"] = "historical-lookup"
            left["documentation"]["visible"] = False
    retained = [
        (phrase, identity)
        for phrase, identity in zip(
            old["aliases"]["commands"], old["aliases"]["command_ids"], strict=True
        )
        if identity not in retired
    ]
    old["aliases"]["commands"] = [phrase for phrase, _ in retained]
    old["aliases"]["command_ids"] = [identity for _, identity in retained]
    old["ocf"]["command_review"] = "approved"
    for key in ("summary", "community_description"):
        old["purpose"][key] = old["purpose"][key].replace("proposed concise cue", "activation cue")
        if owner == "OCF-BOD-014":
            old["purpose"][key] = old["purpose"][key].replace(" for review", "")
    # These two fields record the decision/lookup policy, not behavior.
    old["historical_lookup"] = deepcopy(new.get("historical_lookup"))
    old["compatibility"]["state"] = new["compatibility"]["state"]
    if new["compatibility"]["state"] != "historical-lookup":
        raise OCFError("superseded primary wording must remain historical lookup")
    old["compatibility"]["rationale"] = new["compatibility"]["rationale"]
    if old != new:
        raise OCFError("function change exceeds approved title/cue scope")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def records(root=REPO_ROOT, *, required=False):
    from .cue_migration import contained
    from .validators import _load_schema, validate_against_schema

    result = []
    for name in REGISTERED:
        path = contained(root, name)
        if not path.is_file():
            if required:
                raise OCFError("approved successor record missing: " + name)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_against_schema(data, _load_schema("editorial-cue-migration.schema.json"))
        if errors:
            raise OCFError("invalid editorial successor: " + " | ".join(errors))
        expected = APPROVED.get(data["id"])
        if expected is None or len(data["decisions"]) != 1:
            raise OCFError("unregistered editorial approval")
        row = data["decisions"][0]
        if any(
            row["previous"].get(key) != value
            for key, value in APPROVED_PREDECESSORS[data["id"]].items()
        ):
            raise OCFError("editorial predecessor wording differs from the explicit approval")
        if (
            row["function_id"],
            row["current_title"],
            row["display_cue"],
            row["spoken_cue"],
        ) != expected:
            raise OCFError("editorial successor differs from the explicit approved pair")
        if not isinstance(data.get("predecessor_files"), dict):
            raise OCFError("editorial successor requires exact predecessor files")
        expected_keys = {
            f"{row['narration_file']}::hplus.function.{row['function_id'].lower()}.{role}"
            for role in ("function-body", "closer")
        }
        if {entry["identity"] for entry in data["allowed_text_changes"]} != expected_keys:
            raise OCFError("successor must identify exactly the approved body and closer")
        for changed in data["allowed_text_changes"]:
            allowed = {
                (row["previous"]["spoken_cue"], row["spoken_cue"]),
                (
                    "OCF " + row["previous"]["title"] + " exercise",
                    "OCF " + row["current_title"] + " exercise",
                ),
            }
            if changed["function_id"] != row["function_id"] or not changed["identity"].startswith(
                row["narration_file"] + "::"
            ):
                raise OCFError("successor text change is outside the approved function")
            if any(
                (item["before"], item["after"]) not in allowed for item in changed["substitutions"]
            ):
                raise OCFError("successor substitution is not approved cue/title wording")
        result.append(data)
    return result


def before_file(root, name):
    from .cue_migration import contained

    text = contained(root, name).read_text(encoding="utf-8")
    for data in reversed(records(root)):
        row = data["source_files"].get(name)
        if row is None:
            continue
        if sha(text) != row["after_sha256"]:
            raise OCFError("current editorial successor file drift: " + name)
        prior = data["predecessor_files"].get(name)
        if prior is None or sha(prior) != row["before_sha256"]:
            raise OCFError("editorial predecessor file missing or changed: " + name)
        text = prior
    return text


def before_texts(root, texts):
    from .cue_migration import replay_change

    previous = dict(texts)
    for data in reversed(records(root)):
        for row in data["allowed_text_changes"]:
            current = previous.get(row["identity"])
            if current != replay_change(row):
                raise OCFError("current editorial successor speech drift: " + row["identity"])
            previous[row["identity"]] = row["before_text"]
    return previous


def current_decision_record(root=REPO_ROOT):
    """Derived current view; immutable approval ledgers remain separate."""
    from .cue_migration import decision_record

    result = json.loads(json.dumps(decision_record(root)))
    result["decision_ids"] = [result["id"]]
    by_owner = {row["function_id"]: row for row in result["decisions"]}
    for data in records(root):
        result["id"] = data["id"]
        result["source_commit"] = data["source_commit"]
        result["integrity_baseline"] = data["integrity_baseline"]
        result["decision_ids"].append(data["id"])
        by_owner.update({row["function_id"]: row for row in data["decisions"]})
        result["allowed_text_changes"].extend(data["allowed_text_changes"])
        result["locales_requiring_review"] = sorted(
            set(result["locales_requiring_review"]) | set(data["locales_requiring_review"])
        )
    result["decisions"] = list(by_owner.values())
    return result


def verify(root=REPO_ROOT):
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    from .cue_migration import contained, replay_change

    problems = []
    texts = narration_texts(root)
    file_view = {}

    def read(name):
        return (
            file_view[name]
            if name in file_view
            else contained(root, name).read_text(encoding="utf-8")
        )

    for data in reversed(records(root, required=True)):
        decision = data["decisions"][0]
        function_name = decision["function_file"]
        function_scope(
            yaml.safe_load(data["predecessor_files"][function_name]),
            yaml.safe_load(read(function_name)),
            decision,
        )
        old_narration = yaml.safe_load(data["predecessor_files"][decision["narration_file"]])
        new_narration = yaml.safe_load(read(decision["narration_file"]))
        comparable = deepcopy(new_narration)
        for key in decision["narration_keys_changed"]:
            for field in ("text", "version"):
                comparable["entries"][key][field] = old_narration["entries"][key][field]
            comparable["entries"][key].pop("cue_template", None)
        if comparable != old_narration:
            problems.append("narration provenance or unapproved entries changed")
        previous_path = contained(root, data["previous_integrity_baseline"])
        previous_raw = previous_path.read_text(encoding="utf-8")
        if sha(previous_raw) != data["previous_baseline_sha256"]:
            problems.append("immutable predecessor text baseline changed")
        expected = json.loads(previous_raw)
        allowed = {row["identity"]: row for row in data["allowed_text_changes"]}
        if len(allowed) != len(data["allowed_text_changes"]) or not set(allowed) <= expected.keys():
            raise OCFError("invalid successor text allowlist identities")
        for identity, row in allowed.items():
            if expected[identity] != row["before_sha256"]:
                problems.append("successor predecessor text hash mismatch: " + identity)
            after = replay_change(row)
            if texts.get(identity) != after:
                problems.append("successor resolved speech mismatch: " + identity)
            expected[identity] = sha(after)
            key = identity.split("::", 1)[1]
            raw = yaml.safe_load(read(identity.split("::", 1)[0]))["entries"][key]
            raw_text = raw if isinstance(raw, str) else raw["text"]
            if sha(raw_text) != row.get("raw_template_sha256"):
                problems.append("successor raw template drift: " + identity)
            if (
                raw_text != after.replace(decision["spoken_cue"], "{{ cue.primary }}")
                or not isinstance(raw, dict)
                or raw.get("cue_template")
                != {"function_id": decision["function_id"], "allowed": ["cue.primary"]}
            ):
                problems.append(
                    "successor teaching must use only the approved primary reference: " + identity
                )
        if expected != text_fingerprints(texts):
            problems.append("unapproved protected narration or identity changed")
        baseline = json.loads(
            contained(root, data["integrity_baseline"]).read_text(encoding="utf-8")
        )
        if baseline != expected:
            problems.append("successor baseline differs from approved replay")
        for name, row in data["source_files"].items():
            if sha(read(name)) != row["after_sha256"]:
                problems.append("successor source drift: " + name)
            if row["before_sha256"] is not None:
                if sha(data["predecessor_files"].get(name, "")) != row["before_sha256"]:
                    problems.append("successor predecessor drift: " + name)
        for name, checksum in data["unaffected_function_sha256"].items():
            if sha(read(name)) != checksum:
                problems.append("unapproved function edit: " + name)
        old_raw = contained(root, data["previous_defaults_lock"]).read_text(encoding="utf-8")
        old = json.loads(old_raw)
        new = json.loads(contained(root, data["defaults_lock"]).read_text(encoding="utf-8"))
        if sha(old_raw) != data["previous_defaults_sha256"]:
            problems.append("immutable predecessor defaults changed")
        if old["profiles"] != new["profiles"] or old["files"].keys() != new["files"].keys():
            problems.append("successor engineering profiles/dependencies changed")
        changed_narration = {row["narration_file"] for row in data["decisions"]}
        if any(
            new["files"].get(name) != checksum
            for name, checksum in old["files"].items()
            if name not in changed_narration
        ):
            problems.append("unapproved engineering dependency change")
        file_view.update(data["predecessor_files"])
        for row in data["allowed_text_changes"]:
            texts[row["identity"]] = row["before_text"]
    return problems
