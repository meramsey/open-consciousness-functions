"""Explicit reviewed shared-state symbols, separate from function-owned commands."""

import hashlib
import json

from .paths import REPO_ROOT
from .utils import OCFError, yaml_safe_load


def load(root=REPO_ROOT):
    from .validators import _load_schema, validate_against_schema

    data = yaml_safe_load((root / "function-content/shared-state-cues.yaml").read_text())
    problems = validate_against_schema(data, _load_schema("shared-state-cues.schema.json"))
    if problems:
        raise OCFError("invalid shared state cues: " + " | ".join(problems))
    for symbol, row in data["cues"].items():
        role = symbol.rsplit(".", 1)[1]
        if row["role"] != role or row["id"] != "OCF-SHARED-CUE-ACCESS-" + role.upper():
            raise OCFError("shared state cue identity/role mismatch")
        if row["spoken_key"] != row["display_key"]:
            raise OCFError("shared cue speech/display must reference one locale authority")
    return data


def cue(symbol, locale, catalog, *, registry=None):
    registry = registry or load()
    if symbol not in registry["cues"]:
        raise OCFError("unsupported shared-state selector: " + symbol)
    row = registry["cues"][symbol]
    entry, resolution = catalog.raw_resource(
        row["spoken_key"], locale, domain="narration", fallback=False
    )
    if (
        entry.status not in {"reviewed", "canonical"}
        or entry.cue_template is not None
        or not entry.text.strip()
        or "{" in entry.text
        or "}" in entry.text
    ):
        raise OCFError("shared state cue requires reviewed nonrecursive literal speech")
    return entry.text, {
        "shared_state_id": registry["id"],
        "cue_id": row["id"],
        "key": row["spoken_key"],
        "locale": resolution.origin_locale,
        "kind": "state-intention-not-application-command",
    }


def expand(entry, locale, catalog):
    from .cue_templates import reject_unexpanded, scan

    registry = load()
    contract = entry.cue_template
    if (
        contract.get("shared_state") != registry["id"]
        or entry.domain != "narration"
        or entry.variables
        or entry.status not in {"reviewed", "canonical"}
    ):
        raise OCFError("invalid shared-state narration contract")
    pieces = scan(entry.text)
    used = {part["symbol"] for part in pieces if "symbol" in part}
    allowed = contract.get("allowed", [])
    if not used or len(allowed) != len(set(allowed)) or used != set(allowed):
        raise OCFError("shared-state declared references differ from used references")
    result, references = [], []
    for part in pieces:
        if "text" in part:
            result.append(part["text"])
            continue
        symbol = part["symbol"]
        row = registry["cues"].get(symbol)
        if row is None or entry.key not in row["authorized_resources"]:
            raise OCFError("shared-state cue is not authorized for this narration resource")
        text, provenance = cue(symbol, locale, catalog, registry=registry)
        result.append(text)
        references.append({**part, "text": text, "provenance": provenance})
    resolved = "".join(result)
    reject_unexpanded(resolved)
    return resolved, references


def describe(locale="en-US", *, catalog=None):
    from .locale import LocaleCatalog

    registry = load()
    catalog = (catalog or LocaleCatalog()).with_revision(registry["narration_revision"], locale)
    rows = []
    for symbol, row in registry["cues"].items():
        spoken, provenance = cue(symbol, locale, catalog, registry=registry)
        display, _ = catalog.raw_resource(
            row["display_key"], locale, domain="narration", fallback=False
        )
        item = {
            "id": row["id"],
            "role": row["role"],
            "spoken": spoken,
            "display": display.text,
            "provenance": provenance,
        }
        legacy = row.get("legacy_compatibility")
        if legacy:
            owner = next(
                (r for r in catalog.function_records() if r.id == legacy["function_id"]), None
            )
            command = (
                next((c for c in owner.command_records if c.id == legacy["command_id"]), None)
                if owner
                else None
            )
            previous, _ = catalog.raw_resource(
                legacy["spoken_key"], locale, domain="narration", fallback=False
            )
            label, _ = catalog.raw_resource(
                legacy["display_key"], locale, domain="ui", fallback=False
            )
            if (
                command is None
                or command.role != "access-close"
                or label.text != display.text
                or hashlib.sha256(previous.text.encode()).hexdigest() != legacy["spoken_sha256"]
            ):
                raise OCFError("frozen access-close compatibility record drift")
            item["legacy_compatibility"] = {
                "command_id": command.id,
                "function_id": owner.id,
                "spoken": previous.text,
                "status": "preserved-independent-reviewed-variant",
            }
        rows.append(item)
    return {
        "id": registry["id"],
        "locale": locale,
        "kind": "shared-state-intentions",
        "cues": rows,
        "application_commands": False,
        "release_ready": False,
    }


def run_cli(args):
    print(json.dumps(describe(args.locale), ensure_ascii=False, indent=2))
    return 0
