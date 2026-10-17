"""Historical discovery resolves stable functions, never an activation target."""

from __future__ import annotations

import unicodedata

from .commands import cue_presentation, is_active, resolve_phrase
from .indexes import load_all_functions
from .locale import LocaleCatalog, normalize_tag


def lookup_form(text):
    """Unicode discovery equivalence only; not spoken-cue matching."""
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def lookup(query, *, locale="en-US", records=None, catalog=None):
    catalog = catalog or LocaleCatalog()
    target = normalize_tag(locale) or catalog.canonical_locale
    needle = lookup_form(query)
    rows = []
    if not needle:
        return rows
    for owner in records if records is not None else load_all_functions():
        candidates = [
            (owner.id, "stable-id"),
            (owner.slug, "internal-slug"),
            (owner.canonical_name, "current-title"),
            (owner.canonical_command or "", "current-primary"),
        ]
        candidates += [
            (row["text"], row["kind"]) for row in owner.data.get("historical_lookup", [])
        ]
        candidates += [(owner.data["legacy"]["name"], "historical-source-name")]
        candidates += [
            (name, "historical-name")
            for name in owner.data["aliases"]["names"]
            if name != owner.canonical_name
        ]
        candidates += [(phrase, "historical-source-phrase") for phrase in owner.legacy_commands]
        matched = [
            {
                "text": text,
                "kind": kind,
                "historical": kind not in {"stable-id", "current-title", "current-primary"},
            }
            for text, kind in candidates
            if lookup_form(text) == needle
        ]
        # Provenance and operational availability are different axes. In
        # particular a legacy-backed Release must remain visibly operational.
        for command in owner.command_records:
            if command.designation == "primary" or not is_active(command):
                continue
            phrase = resolve_phrase(owner, command)
            if lookup_form(phrase) == needle:
                matched.append(
                    {
                        "text": phrase,
                        "kind": "current-operational-command"
                        if command.role != "legacy-alias"
                        else "current-compatibility-record",
                        "historical": command.role == "legacy-alias",
                        "command_id": command.id,
                        "role": command.role,
                        "active_record": True,
                    }
                )
        if not matched:
            continue
        docs = owner.documentation
        title = (
            catalog.lookup(docs["title_key"], target, domain="ui", fallback=True)
            if docs.get("title_key")
            else None
        )
        purpose = (
            catalog.lookup(docs["purpose_key"], target, domain="ui", fallback=True)
            if docs.get("purpose_key")
            else None
        )
        rows.append(
            {
                "function_id": owner.id,
                "title": catalog.text(docs["title_key"], target) if title else owner.canonical_name,
                "title_locale": title.origin_locale if title else "canonical-record",
                "purpose": catalog.text(docs["purpose_key"], target)
                if purpose
                else owner.purpose_summary,
                "purpose_locale": purpose.origin_locale if purpose else "canonical-record",
                "cue": cue_presentation(owner, target, catalog=catalog),
                "matches": matched,
                "activation_selected": False,
                "historical_note": "Historical matches never select activation or deactivate current modes/controls. Current OCF intent may differ from its historical source; inspect each match's role and availability.",
            }
        )
    return rows
