"""Literal localized presentation through LocaleCatalog, not another registry."""

from __future__ import annotations

from copy import deepcopy

from .locale import LocaleCatalog, LocalizationError


def metadata(record, locale="en-US", *, catalog=None):
    catalog = catalog or LocaleCatalog()
    resolver = getattr(catalog, "localized_function", None)
    if resolver is None:
        return None  # Legacy key-only catalog adapters remain supported.
    try:
        data, resolution = resolver(record.id, locale, fallback=False)
    except LocalizationError:
        return None
    if not isinstance(data.get("title"), dict) or "text" not in data["title"]:
        return None
    return data


def title(record, locale="en-US", *, catalog=None):
    catalog = catalog or LocaleCatalog()
    key = record.documentation.get("title_key")
    if not key:
        return record.canonical_name  # Unlocalized historical records only.
    if not hasattr(catalog, "resource"):
        return catalog.text(key, locale)
    entry, _ = catalog.resource(key, locale, domain="ui", fallback=True)
    return entry.text


def description(record, locale="en-US", *, catalog=None):
    catalog = catalog or LocaleCatalog()
    key = record.documentation.get("short_description_key") or record.documentation.get(
        "purpose_key"
    )
    if not key:
        return record.purpose_summary
    if not hasattr(catalog, "resource"):
        return catalog.text(key, locale)
    entry, _ = catalog.resource(key, locale, domain="ui", fallback=True)
    return entry.text


def display_command(record, locale="en-US", *, catalog=None):
    from .commands import cue_presentation

    return cue_presentation(record, locale, catalog=catalog)["display_cue"]


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
    return result
