"""Localized cover/metadata text, resolved from existing command and locale authority."""

from __future__ import annotations

import json

from .commands import is_active, localized_cue
from .indexes import load_function_by_id
from .locale import LocaleCatalog, LocalizationError, locale_language, normalize_tag
from .utils import OCFError


def function_artwork_content(function_id, locale="en-US", *, catalog=None, strict=True):
    catalog = catalog or LocaleCatalog()
    record = load_function_by_id(function_id)
    if record is None:
        raise OCFError("unknown artwork function")
    locale = normalize_tag(locale)

    def resource(key, *, optional=False, source_review=False):
        try:
            entry, resolution = catalog.resource(key, locale, domain="ui", fallback=not strict)
        except LocalizationError:
            if optional:
                return None, {"key": key, "status": "missing-for-locale", "locale": locale}
            raise
        if (
            strict
            and entry.status not in {"canonical", "reviewed"}
            and not source_review
            and not (
                optional
                and locale_language(locale) == "en"
                and resolution.origin_locale == "en-US"
                and entry.status == "draft"
            )
        ):
            raise LocalizationError(f"artwork text {key!r} requires locale review")
        return entry.render({}, plural_rules=catalog.plural_rules_for(resolution.origin_locale)), {
            "key": key,
            "requested_locale": locale,
            "resolved_locale": resolution.origin_locale,
            "fallback": resolution.fallback,
            "status": entry.status,
            "version": entry.version,
        }

    def cue(command):
        result = localized_cue(record, command, locale, catalog=catalog, strict=strict)
        if (
            result["binding_status"] == "unbound"
            and locale_language(locale) == "en"
            and not command.localization.get("spoken_cue_key")
        ):
            # Source-English commands without a separate locale key retain their
            # reviewed function-YAML authority for an English regional/parent tag.
            result = localized_cue(record, command, "en-US", catalog=catalog, strict=strict) | {
                "requested_locale": locale,
                "spoken_fallback": locale != "en-US",
            }
        if strict and result["binding_status"] != "resolved":
            raise LocalizationError(f"{command.id}: artwork requires a reviewed cue")
        display_key = command.localization.get("display_cue_key")
        if display_key:
            # localized_cue supports UI fallback generally; artwork strict mode
            # independently forbids cross-language or unreviewed visible labels.
            display, provenance = resource(
                display_key,
                source_review=locale_language(locale) == "en"
                and command.data.get("spoken_review") == "reviewed"
                and result.get("display_locale") == "en-US",
            )
            result = result | {"display_cue": display, "display_resolution": provenance}
        elif strict and locale_language(locale) != "en":
            raise LocalizationError(
                f"{command.id}: reviewed localized display cue binding is missing"
            )
        if strict and locale_language(result.get("spoken_locale", locale)) != locale_language(
            locale
        ):
            raise LocalizationError("artwork cue cannot silently fall back across languages")
        return result

    primary_record = next(
        (c for c in record.command_records if c.designation == "primary" and is_active(c)), None
    )
    primary = cue(primary_record) if primary_record else None
    purpose_key = record.documentation.get("purpose_key")
    purpose, purpose_resolution = resource(purpose_key) if purpose_key else (None, None)
    description, description_resolution = resource(
        f"functions.{function_id.lower()}.artwork-description", optional=True
    )
    return {
        "function_id": function_id,
        "locale": locale,
        "strict_locale": strict,
        "primary": primary,
        "description": description,
        "description_resolution": description_resolution,
        "purpose": purpose,
        "purpose_resolution": purpose_resolution,
        "secondary_commands": [
            cue(c)
            for c in record.command_records
            if c.designation != "primary" and c.role != "legacy-alias" and is_active(c)
        ],
    }


def content_tags(content):
    """Use ordinary textual Vorbis comments / ID3 TXXX fields, not novel frames."""
    primary = content["primary"] or {}
    values = {
        "OCF_PRIMARY_DISPLAY_CUE": primary.get("display_cue"),
        "OCF_PRIMARY_SPOKEN_CUE": primary.get("spoken_cue"),
        "OCF_SHORT_DESCRIPTION": content["description"],
        "OCF_FUNCTION_PURPOSE": content["purpose"],
        "OCF_DESCRIPTION_REVIEW": content["description_resolution"].get("status"),
        "OCF_SECONDARY_COMMANDS": json.dumps(content["secondary_commands"], ensure_ascii=False),
    }
    return {key: value for key, value in values.items() if value is not None}
