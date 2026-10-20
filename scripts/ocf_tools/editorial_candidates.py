"""Explicit, untimed editorial review; never a render or approval API."""

from __future__ import annotations

import argparse
import hashlib
import json

from .audio_defaults import DSP_ID, PACING_ID, TEMPLATE_ID
from .complete_session import _slot_keys, _verify_session_structure
from .cue_templates import expand
from .indexes import load_yaml_file
from .locale import LocaleCatalog, NarrationResource
from .models import function_from_dict
from .paths import REPO_ROOT
from .semantic_dsp import load_profile
from .session import compose, load_pacing_profile, load_template
from .utils import OCFError
from .validators import _load_schema, validate_against_schema

CANDIDATES = {
    "manifest-v2": "OCF-EXP-001",
    "dissolve": "OCF-EXP-003",
    "clear-zone": "OCF-EXP-005",
    "intuition": "OCF-EXP-006",
}
DIRECTORY = REPO_ROOT / "function-content/editorial/candidates"
LEDGER = "function-content/editorial/candidates-001.json"
LEDGER_SHA256 = "8f7a905cd19813ef32ce3edd39534d779c6817113bbc701638cb860a792f677b"


def predecessor(root, name, text):
    """Project the checked additive locale manifest for historical witnesses."""
    path = root / LEDGER
    if not path.is_file():
        return text
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_SHA256:
        raise OCFError("candidate integration ledger drift")
    row = json.loads(raw)["files"].get(name)
    if row is None:
        return text
    if (
        hashlib.sha256(text.encode()).hexdigest() != row["after_sha256"]
        or hashlib.sha256(row["predecessor"].encode()).hexdigest() != row["before_sha256"]
    ):
        raise OCFError("candidate integration source drift: " + name)
    return row["predecessor"]


def context(name: str, *, locale: str = "en-US", root=REPO_ROOT):
    """Resolve registered or staged authority without adding production records."""
    if name not in CANDIDATES or locale != "en-US":
        raise OCFError("candidate review requires a registered candidate and exact en-US locale")
    records = [
        function_from_dict(load_yaml_file(path), path)
        for path in sorted((root / "functions").rglob("*.yaml"))
    ]
    from .candidate_approval import record as approval_record

    approval = approval_record(root)
    registered = any(row.id == CANDIDATES[name] for row in records)
    if name == "intuition" and not (registered and approval):
        path = root / "function-content/editorial/candidates/intuition.function.yaml"
        data = load_yaml_file(path)
        errors = validate_against_schema(data, _load_schema("function.schema.json"))
        if errors:
            raise OCFError("invalid candidate function: " + " | ".join(errors))
        if any(record.id == data["id"] for record in records):
            raise OCFError("staged Intuition identity collides with the live registry")
        records.append(function_from_dict(data, path))
    owner = next(record for record in records if record.id == CANDIDATES[name])
    catalog = LocaleCatalog(root / "locales", function_records=lambda: records)
    if name == "intuition" and not registered:
        command = owner.command_records[0]
        key = "commands." + command.id.lower() + ".spoken-cue"
        catalog.canonical.entries[key] = NarrationResource(
            key, locale, "narration", command.data["spoken"], status="draft"
        )
    return owner, catalog


def review(name: str, *, locale: str = "en-US") -> dict:
    """Validate and expand one explicit draft without mutating live resources."""
    from .candidate_approval import record as approval_record
    from .commands import load_procedure_catalog, resolve_phrase, resolve_procedure
    from .cue_templates import value as cue_value

    owner, catalog = context(name, locale=locale)
    approval = approval_record()
    path = DIRECTORY / f"{name}.en-US.yaml"
    data = load_yaml_file(path)
    errors = validate_against_schema(data, _load_schema("locale-resource.schema.json"))
    if errors:
        raise OCFError("invalid candidate resource: " + " | ".join(errors))
    sequence = owner.data["narration"]["sequence"]
    if set(data["entries"]) != {row["key"] for row in sequence}:
        raise OCFError("candidate resources differ from the function-owned sequence")
    entries = []
    for row in sequence:
        value = data["entries"][row["key"]]
        if value["status"] != "draft":
            raise OCFError("candidate review cannot promote narration")
        entry = NarrationResource(
            row["key"],
            locale,
            "narration",
            value["text"],
            status="draft",
            version=value["version"],
            cue_template=value.get("cue_template"),
        )
        text, references = (
            expand(entry, locale, catalog, draft_review=True)
            if entry.cue_template
            else (entry.text, [])
        )
        entries.append(
            {
                **row,
                "version": entry.version,
                "status": "draft",
                "text": text,
                "raw_template": entry.text,
                "notes": value.get("notes"),
                "raw_template_sha256": hashlib.sha256(entry.text.encode()).hexdigest(),
                "resolved_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "references": references,
            }
        )
    binding = {"narration_plan": owner.data["narration"]}
    template = load_template(TEMPLATE_ID)
    document = compose(
        template,
        {},
        title=owner.canonical_name,
        slot_keys=_slot_keys(binding, template),
        pacing_profile=load_pacing_profile(PACING_ID),
    )
    _verify_session_structure(document, binding, load_profile(DSP_ID))
    commands = []
    for command in owner.command_records:
        if command.data.get("availability", "active") != "active" or command.role == "legacy-alias":
            continue
        spoken, provenance = cue_value(
            owner, "cue.id." + command.id, locale, catalog, draft_review=True
        )
        commands.append(
            {
                "id": command.id,
                "role": command.role,
                "designation": command.designation,
                "display": resolve_phrase(owner, command),
                "spoken": spoken,
                "procedure": command.procedure,
                "steps": resolve_procedure(command, load_procedure_catalog()),
            }
        )
    return {
        "candidate": name,
        "function_id": owner.id,
        "locale": locale,
        "title": owner.canonical_name,
        "registration": "staged proposal" if name == "intuition" and not approval else "registered",
        "authority": owner.path.relative_to(REPO_ROOT).as_posix(),
        "narration_authority": path.relative_to(REPO_ROOT).as_posix(),
        "purpose": owner.data["purpose"],
        "lifecycle": owner.data["lifecycle"],
        "commands": commands,
        "pending_approval": not bool(approval),
        "editorial_status": "approved" if approval else "draft",
        "approval_id": approval["id"] if approval else None,
        "snapshot_status": "draft",
        "production_authorized": bool(approval),
        "release_ready": False,
        "timing": "unmeasured editorial preview",
        "entries": entries,
        "semantic_plan": document,
        "procedure": [
            command.procedure
            for command in owner.command_records
            if command.data.get("availability", "active") == "active"
        ],
    }


def discover():
    """Compact discovery for CLI/MCP; full speech is an explicit preview."""
    return [
        {
            key: result[key]
            for key in (
                "candidate",
                "function_id",
                "title",
                "registration",
                "editorial_status",
                "pending_approval",
                "authority",
                "commands",
            )
        }
        for result in (review(name) for name in CANDIDATES)
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=CANDIDATES)
    parser.add_argument("--locale", default="en-US")
    args = parser.parse_args(argv)
    print(json.dumps(review(args.candidate, locale=args.locale), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
