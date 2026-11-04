"""Literal localized presentation through LocaleCatalog, not another registry."""

from __future__ import annotations

from copy import deepcopy

from .locale import LocaleCatalog, LocalizationError


def metadata(record, locale="en-US", *, catalog=None):
    function_id = getattr(record, "id", None)
    if function_id is None:
        return None
    catalog = catalog or LocaleCatalog()
    resolver = getattr(catalog, "localized_function", None)
    if resolver is None:
        return None  # Legacy key-only catalog adapters remain supported.
    try:
        data, resolution = resolver(function_id, locale, fallback=False)
    except LocalizationError:
        return None
    if not isinstance(data.get("title"), dict) or "text" not in data["title"]:
        return None
    return data


def title(record, locale="en-US", *, catalog=None):
    key = (getattr(record, "documentation", None) or {}).get("title_key")
    if not key:
        return record.canonical_name  # Unlocalized historical records only.
    catalog = catalog or LocaleCatalog()
    if not hasattr(catalog, "resource"):
        return catalog.text(key, locale)
    entry, _ = catalog.resource(key, locale, domain="ui", fallback=True)
    return entry.text


def description(record, locale="en-US", *, catalog=None):
    documentation = getattr(record, "documentation", None) or {}
    key = documentation.get("short_description_key") or documentation.get("purpose_key")
    if not key:
        return record.purpose_summary
    catalog = catalog or LocaleCatalog()
    if not hasattr(catalog, "resource"):
        return catalog.text(key, locale)
    entry, _ = catalog.resource(key, locale, domain="ui", fallback=True)
    return entry.text


def display_command(record, locale="en-US", *, catalog=None):
    from .commands import cue_presentation

    if not getattr(record, "command_records", []):
        return record.canonical_command or ""
    cue = cue_presentation(record, locale, catalog=catalog)
    return cue["display_cue"] if cue else record.canonical_command or ""


def registry_projection(record, locale="en-US", *, catalog=None):
    """Keep the legacy discovery shape while deriving localized presentation.

    The global FunctionRecord is never mutated: IDs, behavior, history and
    structural command references remain available exactly as registered.
    """
    catalog = catalog or LocaleCatalog()
    result = deepcopy(record.data)
    result["canonical"]["name"] = title(record, locale, catalog=catalog)
    result["canonical"]["command"]["primary"] = display_command(record, locale, catalog=catalog)
    result["purpose"]["summary"] = description(record, locale, catalog=catalog)
    localized = metadata(record, locale, catalog=catalog)
    if localized is not None:
        result["tags"] = deepcopy(localized.get("tags", []))
        result["use_cases"] = deepcopy(localized.get("common_uses", []))
        result["localized_relationships"] = deepcopy(localized.get("relationships", {}))
    return result


def matches(record, locale="en-US", *, catalog=None, tag=None, query=None):
    """Discovery only: never selects a command or changes historical lookup."""
    from .vocabulary import lookup_form

    data = metadata(record, locale, catalog=catalog) or {}
    if tag and lookup_form(tag) not in {
        lookup_form(value)
        for v in data.get("tags", [])
        for value in (v["text"], v.get("semantic_id", v["text"]))
    }:
        return False
    if query:
        values = [
            record.id,
            title(record, locale, catalog=catalog),
            description(record, locale, catalog=catalog),
        ]
        values += [v["text"] for field in ("tags", "common_uses") for v in data.get(field, [])]
        if not any(lookup_form(query) in lookup_form(value) for value in values):
            return False
    return True
