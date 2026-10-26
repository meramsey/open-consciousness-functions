"""Strict, nonrecursive cue interpolation; all locale lookup uses LocaleCatalog.

Only {{ documented.symbol }} is executable syntax. Backslash escapes a single
brace or backslash. Values are complete reviewed cues, never expressions.
"""

from __future__ import annotations

import hashlib
import re

from .commands import cue_presentation, is_active, localized_cue
from .utils import OCFError

ROLES = {
    "cue.mode.increase": "increase",
    "cue.mode.decrease": "decrease",
    "cue.release": "release",
    "cue.cancel": "cancel",
    "cue.close": "close",
    "cue.retrieval": "retrieval",
    "cue.access_close": "access-close",
}
SYMBOL = re.compile(
    r"(?:cue\.(?:primary|mode\.(?:increase|decrease)|release|cancel|close|retrieval|access_close|id\.OCF-CMD-[A-Z0-9-]+)(?:\.variant\.[a-z][a-z0-9_-]*)?|function\.title)\Z"
)


class CueTemplateError(OCFError):
    """Semantic template errors must fail even in a labeled fallback audition."""


def scan(text):
    """Return literal/symbol spans with exact code-point offsets; no normalization."""
    result, cursor, literal = [], 0, []
    while cursor < len(text):
        if text[cursor] == "\\" and cursor + 1 < len(text) and text[cursor + 1] in "{}\\":
            literal.append(text[cursor + 1])
            cursor += 2
        elif text.startswith("{{", cursor):
            if literal:
                result.append({"text": "".join(literal)})
                literal = []
            end = text.find("}}", cursor + 2)
            if end < 0:
                raise CueTemplateError(f"unclosed cue reference at offset {cursor}")
            body = text[cursor + 2 : end].strip()
            if not SYMBOL.fullmatch(body):
                raise CueTemplateError(
                    f"unknown or malformed cue reference {body!r} at offset {cursor}"
                )
            result.append({"symbol": body, "start": cursor, "end": end + 2})
            cursor = end + 2
        elif text.startswith("}}", cursor):
            raise CueTemplateError(f"unexpected closing cue delimiter at offset {cursor}")
        elif text[cursor] in "{}":
            raise CueTemplateError(
                f"unescaped literal brace at offset {cursor}; use backslash escaping or a documented double-brace reference"
            )
        else:
            literal.append(text[cursor])
            cursor += 1
    if literal:
        result.append({"text": "".join(literal)})
    return result


def select_command(owner, symbol):
    base = symbol.split(".variant.", 1)[0]
    commands = [command for command in owner.command_records if is_active(command)]
    if base == "cue.primary":
        matches = [command for command in commands if command.designation == "primary"]
    elif base in ROLES:
        matches = [command for command in commands if command.role == ROLES[base]]
    elif base.startswith("cue.id."):
        matches = [command for command in commands if command.id == base.removeprefix("cue.id.")]
    else:
        raise CueTemplateError(f"unsupported cue selector: {base}")
    if len(matches) != 1:
        raise CueTemplateError(
            f"{owner.id}: {base} resolves {len(matches)} active commands; require a unique role or explicit stable ID"
        )
    if matches[0].function_id != owner.id:
        raise CueTemplateError(f"{owner.id}: selected command belongs to a different function")
    return matches[0]


def choices(owner):
    result = ["function.title"]
    for selector in ("cue.primary", *ROLES):
        try:
            select_command(owner, selector)
        except CueTemplateError:
            continue
        result.append(selector)
    result += ["cue.id." + command.id for command in owner.command_records if is_active(command)]
    for selector in list(result):
        if selector == "function.title":
            continue
        command = select_command(owner, selector)
        variants = set(command.data.get("spoken_variants", {})) | set(
            command.localization.get("spoken_variant_keys", {})
        )
        result.extend(selector + ".variant." + name for name in sorted(variants))
    return result


def value(owner, symbol, locale, catalog, *, draft_review=False):
    if symbol == "function.title":
        key = owner.documentation.get("title_key")
        if not key:
            raise CueTemplateError(f"{owner.id}: missing localized title binding")
        entry, resolution = catalog.raw_resource(key, locale, domain="ui", fallback=False)
        if resolution.origin_locale != "en-US" and entry.status not in {"reviewed", "canonical"}:
            raise CueTemplateError(f"{owner.id}: localized title requires review")
        if resolution.origin_locale == "en-US" and entry.text != owner.canonical_name:
            raise CueTemplateError(
                f"{owner.id}: en-US title conflicts with authoritative function YAML"
            )
        return entry.text, {"key": key, "locale": resolution.origin_locale, "function_id": owner.id}
    command = select_command(owner, symbol)
    if draft_review and command.data.get("spoken_review") == "unresolved":
        return draft_cue(owner, command, locale, catalog)
    if ".variant." in symbol:
        variant = symbol.split(".variant.", 1)[1]
        key = command.localization.get("spoken_variant_keys", {}).get(variant)
        if locale == "en-US":
            row = command.data.get("spoken_variants", {}).get(variant, {})
            if row.get("status") != "reviewed" or not row.get("text"):
                raise CueTemplateError(f"{command.id}: unreviewed or missing variant {variant}")
            return row["text"], {"command_id": command.id, "variant": variant, "locale": "en-US"}
        if not key:
            raise CueTemplateError(f"{command.id}: no localized binding for variant {variant}")
        entry, resolution = catalog.raw_resource(key, locale, domain="narration", fallback=False)
        if entry.status not in {"reviewed", "canonical"}:
            raise CueTemplateError(f"{command.id}: localized variant needs review")
        return entry.text, {
            "command_id": command.id,
            "key": key,
            "locale": resolution.origin_locale,
            "variant": variant,
        }
    resolved = localized_cue(owner, command, locale, catalog=catalog, strict=True)
    if resolved.get("spoken_locale") == "en-US" and (
        not command.data.get("spoken") or command.data.get("spoken_review") != "reviewed"
    ):
        raise CueTemplateError(
            f"{command.id}: symbolic English speech requires authoritative reviewed function-YAML wording"
        )
    if resolved["binding_status"] != "resolved" or not resolved["spoken_cue"]:
        raise CueTemplateError(f"{command.id}: no reviewed spoken cue for {locale}")
    return resolved["spoken_cue"], resolved


def draft_cue(owner, command, locale, catalog):
    """Inspect proposed vocabulary without authorizing production speech."""
    if owner.data.get("audio", {}).get("script_status") != "draft":
        raise CueTemplateError(f"{owner.id}: proposed cues require a draft function")
    key = command.localization.get("spoken_cue_key")
    if not key:
        raise CueTemplateError(f"{command.id}: missing proposed locale cue binding")
    entry, resolution = catalog.raw_resource(key, locale, domain="narration", fallback=False)
    if entry.cue_template is not None or "{" in entry.text or "}" in entry.text:
        raise CueTemplateError(f"{command.id}: proposed cue must be literal")
    if not entry.text.strip() or entry.status != "draft":
        raise CueTemplateError(f"{command.id}: proposed cue must have draft status and text")
    if resolution.origin_locale == "en-US" and entry.text != command.data.get("spoken"):
        raise CueTemplateError(f"{command.id}: proposed cue conflicts with function YAML")
    return entry.text, {
        "command_id": command.id,
        "key": key,
        "locale": resolution.origin_locale,
        "status": "draft",
        "production_authorized": False,
    }


def expand(entry, locale, catalog, *, draft_review=False):
    contract = entry.cue_template
    owner_id = contract.get("function_id")
    try:
        if draft_review and entry.status != "draft":
            raise CueTemplateError("draft review requires a draft narration resource")
        if entry.domain != "narration":
            raise CueTemplateError("cue templates are authorized only for narration resources")
        if entry.variables:
            raise CueTemplateError("symbolic resources cannot accept caller-supplied ICU variables")
        owners = [record for record in catalog.function_records() if record.id == owner_id]
        if len(owners) != 1:
            raise CueTemplateError(f"owner {owner_id!r} resolves {len(owners)} times")
        owner = owners[0]
        canonical = catalog.canonical
        source = canonical.get(entry.key) if canonical else None
        if source is not None and source.cue_template is not None and source.locale != entry.locale:
            if source.cue_template.get("function_id") != owner_id:
                raise CueTemplateError("translation changed the function owner")

            def identities(symbols):
                return {
                    "function.title"
                    if symbol == "function.title"
                    else select_command(owner, symbol).id
                    for symbol in symbols
                }

            if identities(source.cue_template.get("allowed", [])) != identities(
                contract.get("allowed", [])
            ):
                raise CueTemplateError(
                    "translation changed the authorized cue identities; grammar variants must retain the same command"
                )
        authorized = {row["key"] for row in (owner.data.get("narration") or {}).get("sequence", [])}
        if entry.key not in authorized:
            raise CueTemplateError("resource is not an authoritative function narration binding")
        pieces = scan(entry.text)
        used = {piece["symbol"] for piece in pieces if "symbol" in piece}
        allowed = contract.get("allowed", [])
        if len(allowed) != len(set(allowed)) or used != set(allowed):
            raise CueTemplateError(
                f"declared references differ from used references: used={sorted(used)}, declared={allowed}"
            )
        result, references = [], []
        for piece in pieces:
            if "text" in piece:
                result.append(piece["text"])
                continue
            text, provenance = value(
                owner, piece["symbol"], locale, catalog, draft_review=draft_review
            )
            if not isinstance(text, str) or not text.strip() or "{" in text or "}" in text:
                raise CueTemplateError(
                    f"{piece['symbol']}: empty/circular/nested cue value is forbidden"
                )
            result.append(text)
            references.append({**piece, "text": text, "provenance": provenance})
        resolved = "".join(result)
        reject_unexpanded(resolved)
        return resolved, references
    except OCFError as exc:
        raise CueTemplateError(f"{owner_id}/{locale}/{entry.key}: {exc}") from exc


def reject_unexpanded(text):
    if "{{" in text or "}}" in text:
        raise CueTemplateError(
            "unresolved symbolic delimiters in final narration; resolve the resource before synthesis/recording/export"
        )


def preview(function_id, locale="en-US", *, catalog=None, records=None):
    from .indexes import load_all_functions
    from .locale import LocaleCatalog

    records = records if records is not None else load_all_functions()
    catalog = catalog or LocaleCatalog(function_records=lambda: records)
    owner = next((record for record in records if record.id == function_id), None)
    if owner is None:
        raise CueTemplateError(f"unknown function {function_id}")
    resources = []
    for binding in (owner.data.get("narration") or {}).get("sequence", []):
        entry, resolution = catalog.resource(
            binding["key"], locale, domain="narration", fallback=False
        )
        raw = entry.raw_template if entry.raw_template is not None else entry.text
        resources.append(
            {
                **binding,
                "source_template": raw,
                "resolved_text": entry.text,
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "resolved_sha256": hashlib.sha256(entry.text.encode()).hexdigest(),
                "locale": resolution.origin_locale,
                "references": list(entry.cue_provenance),
            }
        )
    title_key = owner.documentation.get("title_key")
    title_resolution = (
        catalog.lookup(title_key, locale, domain="ui", fallback=True) if title_key else None
    )
    return {
        "function_id": owner.id,
        "source_title": owner.canonical_name,
        "localized_title": catalog.text(title_key, locale) if title_key else owner.canonical_name,
        "title_locale": title_resolution.origin_locale if title_resolution else "canonical-record",
        "cue_presentation": cue_presentation(owner, locale, catalog=catalog),
        "requested_locale": locale,
        "resources": resources,
        "synthesis": False,
    }
