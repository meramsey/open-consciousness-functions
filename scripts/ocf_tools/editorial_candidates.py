"""Read-only previews of previously approved, now-canonical functions."""

from __future__ import annotations

import argparse
import hashlib
import json

from .audio_defaults import DSP_ID, PACING_ID, TEMPLATE_ID
from .complete_session import _slot_keys, _verify_session_structure
from .cue_templates import expand
from .indexes import load_all_functions, load_function_by_id
from .locale import LocaleCatalog, NarrationResource
from .paths import REPO_ROOT
from .semantic_dsp import load_profile
from .session import compose, load_pacing_profile, load_template
from .utils import OCFError

CANDIDATES = {
    "manifest-v2": "OCF-EXP-001",
    "dissolve": "OCF-EXP-003",
    "clear-zone": "OCF-EXP-005",
    "intuition": "OCF-EXP-006",
}


def context(name: str, *, locale: str = "en-US", root=REPO_ROOT):
    """Resolve the registered function and its own locale resource only."""
    if name not in CANDIDATES:
        raise OCFError("unknown approved function preview")
    if locale != "en-US":
        raise OCFError("approved function preview is available only in its reviewed en-US locale")
    owner = load_function_by_id(CANDIDATES[name], root=root)
    if owner is None:
        raise OCFError("canonical function resource is missing: " + CANDIDATES[name])
    catalog = LocaleCatalog(
        root / "locales", function_records=lambda: load_all_functions(root=root)
    )
    localized = catalog.require(locale).localized_functions.get(owner.id)
    if not localized:
        raise OCFError("canonical localized function resource is missing: " + owner.id)
    if not localized.get("record_metadata", {}).get("editorial_approval"):
        raise OCFError("function has no canonical editorial approval metadata: " + owner.id)
    return owner, catalog


def review(name: str, *, locale: str = "en-US") -> dict:
    """Return an untimed read-only preview projected from canonical function data."""
    from .commands import load_procedure_catalog, resolve_phrase, resolve_procedure
    from .cue_templates import value as cue_value

    owner, catalog = context(name, locale=locale)
    localized = catalog.require(locale).localized_functions[owner.id]
    approval = localized["record_metadata"]["editorial_approval"]
    sequence = owner.data["narration"]["sequence"]
    entries = []
    for row in sequence:
        value = localized["entries"].get(row["key"])
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            raise OCFError("canonical narration entry is missing: " + row["key"])
        entry = NarrationResource(
            row["key"],
            locale,
            "narration",
            value["text"],
            status=value.get("status"),
            version=value.get("version"),
            cue_template=value.get("cue_template"),
        )
        text, references = (
            expand(entry, locale, catalog) if entry.cue_template else (entry.text, [])
        )
        entries.append(
            {
                **row,
                "version": entry.version,
                "status": entry.status,
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
        spoken, _provenance = cue_value(owner, "cue.id." + command.id, locale, catalog)
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
        "registration": "registered",
        "authority": owner.path.relative_to(REPO_ROOT).as_posix(),
        "narration_authority": owner.path.relative_to(REPO_ROOT).as_posix(),
        "purpose": owner.data["purpose"],
        "lifecycle": owner.data["lifecycle"],
        "commands": commands,
        "pending_approval": False,
        "editorial_status": "approved and implemented",
        "approval_id": approval["approval_id"],
        "snapshot_status": "canonical",
        "production_authorized": True,
        "release_ready": False,
        "listening_approval": False,
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
    """Compact read-only catalog view; full narration is opt-in."""
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


def verify_approvals(root=REPO_ROOT) -> list[str]:
    """Verify embedded approval hashes against the canonical resolved entries."""
    from .function_catalog import load_functions

    errors = []
    owners = {row.id: row for row in load_functions(root)}
    catalog = LocaleCatalog(
        root / "locales", function_records=lambda: load_all_functions(root=root)
    )
    for name, identity in CANDIDATES.items():
        owner = owners.get(identity)
        localized = catalog.require("en-US").localized_functions.get(identity)
        if owner is None or localized is None:
            errors.append(f"canonical approved function is missing: {identity}")
            continue
        approval = localized.get("record_metadata", {}).get("editorial_approval")
        if not approval or approval.get("decision") != "approve_full_draft":
            errors.append(f"canonical editorial approval is missing or invalid: {identity}")
            continue
        try:
            preview = review(name)
        except OCFError as exc:
            errors.append(f"canonical approved preview failed for {identity}: {exc}")
            continue
        resolved = {row["key"]: row["resolved_text_sha256"] for row in preview["entries"]}
        if resolved != approval.get("resolved_text_sha256"):
            errors.append(f"canonical approved narration hash mismatch: {identity}")
        if approval.get("listening_approval") or approval.get("release_ready"):
            errors.append(f"narration approval was promoted beyond its recorded scope: {identity}")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=CANDIDATES)
    parser.add_argument("--locale", default="en-US")
    args = parser.parse_args(argv)
    print(json.dumps(review(args.candidate, locale=args.locale), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
