"""Checked zero-spoken-drift successor for remaining active literal cue spans."""

import json

import yaml

from .cue_headers import sha
from .paths import REPO_ROOT
from .utils import OCFError

LEDGER = "function-content/editorial/cue-completion-001.json"


def predecessor(root, name, text):
    from .editorial_candidates import predecessor as before_candidates

    text = before_candidates(root, name, text)
    path = root / LEDGER
    if not path.is_file():
        return text
    data = json.loads(path.read_text(encoding="utf-8"))
    row = data["files"].get(name)
    if row is None:
        return text
    old = row["predecessor"]
    if sha(text) != row["after_sha256"] or sha(old) != row["before_sha256"]:
        raise OCFError("cue completion source fingerprint drift: " + name)
    before, after = yaml.safe_load(old), yaml.safe_load(text)
    if name.startswith("audio/session-plans/en-US/"):
        if name.endswith("/_shared.json"):
            for key in ("defaults_lock", "defaults_sha256"):
                before[key] = after[key]
        else:
            before["defaults"]["sha256"] = after["defaults"]["sha256"]
            templates = {
                entry["key"]: entry["raw_template_sha256"]
                for source in data["files"].values()
                for entry in source["entries"]
            }
            for resource in before["resources"]:
                if resource["key"] in templates:
                    resource["raw_template_sha256"] = templates[resource["key"]]
    elif name.startswith("locales/en-US/hplus-"):
        for entry in row["entries"]:
            key = entry["key"]
            template = before["entries"][key]["text"]
            end = len(template)
            for span in reversed(entry["spans"]):
                start, stop = span["start"], span["end"]
                if not 0 <= start < stop <= end or template[start:stop] != span["spoken"]:
                    raise OCFError("cue completion span overlap/mismatch: " + key)
                template = template[:start] + "{{ " + span["symbol"] + " }}" + template[stop:]
                end = start
            if sha(template) != entry["raw_template_sha256"]:
                raise OCFError("cue completion template fingerprint drift: " + key)
            before["entries"][key]["text"] = template
            before["entries"][key]["cue_template"] = entry["contract"]
    else:
        raise OCFError("cue completion path outside authorized scope")
    if before != after:
        raise OCFError("cue completion changed non-cue data: " + name)
    return old


def verify(root=REPO_ROOT):
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    from .cue_migration import contained
    from .validators import _load_schema, validate_against_schema

    path = root / LEDGER
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_against_schema(data, _load_schema("cue-completion-successor.schema.json"))
    if errors:
        return errors
    for name in data["files"]:
        predecessor(root, name, contained(root, name).read_text(encoding="utf-8"))
    if text_fingerprints(narration_texts(root)) != data["resolved_text_sha256"]:
        errors.append("cue completion changed resolved speech")
    old_raw = contained(root, data["previous_defaults_lock"]).read_text(encoding="utf-8")
    old = json.loads(old_raw)
    new = json.loads(contained(root, data["defaults_lock"]).read_text(encoding="utf-8"))
    if sha(old_raw) != data["previous_defaults_sha256"]:
        errors.append("cue completion predecessor lock changed")
    if old["profiles"] != new["profiles"] or old["files"].keys() != new["files"].keys():
        errors.append("cue completion engineering configuration changed")
    for name, checksum in old["files"].items():
        if new["files"].get(name) != data["files"].get(name, {}).get("after_sha256", checksum):
            errors.append("cue completion unrelated dependency changed: " + name)
    return errors
