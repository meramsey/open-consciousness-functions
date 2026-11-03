"""Literal localized presentation through LocaleCatalog, not another registry."""

from __future__ import annotations

from .locale import LocaleCatalog, LocalizationError


def metadata(record, locale="en-US", *, catalog=None):
    catalog = catalog or LocaleCatalog()
    try:
        data, resolution = catalog.localized_function(record.id, locale, fallback=False)
    except LocalizationError:
        return None
    if not isinstance(data.get("title"), dict) or "text" not in data["title"]:
        return None
    return data


def title(record, locale="en-US", *, catalog=None):
    catalog = catalog or LocaleCatalog()
    entry, _ = catalog.resource(
        record.documentation["title_key"], locale, domain="ui", fallback=True
    )
    return entry.text


def description(record, locale="en-US", *, catalog=None):
    catalog = catalog or LocaleCatalog()
    entry, _ = catalog.resource(
        record.documentation["short_description_key"], locale, domain="ui", fallback=True
    )
    return entry.text


def display_command(record, locale="en-US", *, catalog=None):
    from .commands import cue_presentation

    return cue_presentation(record, locale, catalog=catalog)["display_cue"]
