"""Localized command guides built from canonical function records and UI packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .commands import command_view
from .indexes import load_all_functions
from .locale import UI_DOMAIN, LocaleCatalog, LocalizationError, normalize_tag
from .models import FunctionRecord
from .utils import OCFError, generated_content, write_text_atomic


class CommandDocumentationError(OCFError):
    """Command reference metadata cannot be resolved safely."""


GUIDE_KEYS = (
    "command.guide.index-title",
    "command.guide.quick-title",
    "command.guide.function",
    "command.guide.function-count",
    "command.guide.command-count",
    "command.guide.phrase",
    "command.guide.role",
    "command.guide.usage",
    "command.guide.other-commands",
    "command.guide.summary",
    "command.guide.purpose",
    "command.guide.effects",
    "command.guide.procedure",
    "command.guide.relationships",
    "command.guide.observed",
    "command.guide.source-status",
    "command.guide.source-auth-note",
    "command.guide.command-review",
    "command.guide.scope",
    "command.scope.temporary",
    "command.scope.permanent",
    "command.scope.access-channel-close",
    "command.guide.fallback-note",
    "command.guide.canonical-note",
    "command.guide.no-procedure",
    "command.source.available",
    "command.source.unavailable",
    "command.source.pending-source-review",
    "command.review.approved",
    "command.review.pending",
    "command.review.needs-review",
    "command.review.review-required",
    "command.review.superseded",
    "command.relationship.pairs-with",
    "command.relationship.modifies",
    "command.relationship.releases",
    "command.relationship.cancels",
    "command.relationship.retrieves",
    "command.relationship.closes",
) + tuple(
    f"command.procedure-heading.{role}"
    for role in (
        "activation",
        "mode",
        "increase",
        "decrease",
        "retrieval",
        "close",
        "cancel",
        "release",
        "access-close",
        "legacy-alias",
        "auxiliary",
    )
)


def _localized(
    catalog: LocaleCatalog,
    key: str,
    locale: str,
) -> dict[str, Any]:
    try:
        resolution = catalog.lookup(key, locale, domain=UI_DOMAIN, fallback=True)
    except LocalizationError as exc:
        raise CommandDocumentationError(
            f"required command documentation UI key {key!r} is unavailable for {locale}: {exc}"
        ) from exc
    pack = catalog.require(resolution.origin_locale)
    entry = pack.get(key)
    if entry is None:
        raise CommandDocumentationError(f"UI key {key!r} resolved but has no resource entry")
    return {
        "key": key,
        "text": entry.render({}, plural_rules=catalog.plural_rules_for(resolution.origin_locale)),
        "requested_locale": resolution.locale,
        "resolved_locale": resolution.origin_locale,
        "fallback": resolution.fallback,
    }


def _function_document(
    record: FunctionRecord,
    locale: str,
    catalog: LocaleCatalog,
) -> dict[str, Any]:
    docs = record.documentation
    localized: dict[str, Any] = {}
    for field in ("title_key", "short_description_key", "purpose_key", "effect_key"):
        key = docs.get(field)
        if key:
            localized[field.removesuffix("_key")] = _localized(catalog, key, locale)
    if not localized.get("title"):
        raise CommandDocumentationError(f"{record.id} has no localized function-title key")
    if not localized.get("short_description") or not localized.get("purpose"):
        raise CommandDocumentationError(
            f"{record.id} has incomplete localized function documentation"
        )
    source_key = f"command.source.{record.source_availability}"
    source_label = _localized(catalog, source_key, locale)
    review_key = f"command.review.{record.command_review}"
    review_label = _localized(catalog, review_key, locale)
    scope_key = f"command.scope.{record.persistence}"
    persistence_label = _localized(catalog, scope_key, locale)

    commands = []
    for metadata in sorted(
        record.command_records,
        key=lambda item: (
            item.documentation.get("order", 999),
            item.id,
        ),
    ):
        view = command_view(record, metadata)
        command_localized = metadata.localization
        for field in ("label_key", "usage_key", "explanation_key"):
            key = command_localized.get(field)
            if not key:
                raise CommandDocumentationError(f"{record.id}/{metadata.id} lacks {field}")
            view[field.removesuffix("_key")] = _localized(catalog, key, locale)
        purpose_key = command_localized.get("purpose_key")
        if purpose_key:
            view["purpose"] = _localized(catalog, purpose_key, locale)

        steps = view.pop("resolved_procedure_steps", None)
        procedure = view.get("procedure") or {}
        localized_steps = []
        if steps is None:
            view["procedure_steps"] = []
            view["procedure_status"] = str(procedure.get("status", "not-specified"))
        else:
            view["procedure_status"] = str(procedure.get("status", "documented"))
            for step in steps:
                step_key = step.get("localization_key") or (
                    "command.procedure." + str(step["operation"])
                )
                localized_steps.append(
                    {
                        "id": step["id"],
                        "operation": step["operation"],
                        "instruction": _localized(catalog, str(step_key), locale),
                    }
                )
        view["procedure_steps"] = localized_steps

        related_commands = []
        for relation, target_ids in (view.get("relationships") or {}).items():
            relation_key = f"command.relationship.{relation.replace('_', '-')}"
            relation_label = _localized(catalog, relation_key, locale)
            targets = []
            for target_id in target_ids:
                target = next(
                    (item for item in record.command_records if item.id == target_id), None
                )
                if target is None:
                    raise CommandDocumentationError(
                        f"{record.id}/{metadata.id} refers to unknown related command {target_id}"
                    )
                targets.append({"id": target.id, "phrase": command_view(record, target)["phrase"]})
            related_commands.append(
                {"kind": relation, "label": relation_label, "commands": targets}
            )
        view["related_commands"] = related_commands
        if metadata.role == "access-close" and not view.get("effect_scope"):
            command_scope_key = "command.scope.access-channel-close"
        else:
            command_scope_key = f"command.scope.{view.get('effect_scope', record.persistence)}"
        view["scope_label"] = _localized(catalog, command_scope_key, locale)
        commands.append(view)

    return {
        "function_id": record.id,
        "slug": record.slug,
        "title": localized["title"],
        "short_description": localized["short_description"],
        "purpose": localized["purpose"],
        "effects": localized.get("effect"),
        "canonical_command_review": record.command_review,
        "source_availability": record.source_availability,
        "source_availability_label": source_label,
        "command_review_label": review_label,
        "persistence": record.persistence,
        "persistence_label": persistence_label,
        "reimplementation_status": record.reimplementation_status,
        "commands": commands,
    }


def build_command_index(locale: str | None = None, catalog: LocaleCatalog | None = None) -> dict:
    """Resolve the complete localized command data view with fallback provenance."""
    catalog = catalog or LocaleCatalog()
    if catalog.problems:
        raise CommandDocumentationError("locale catalog: " + " | ".join(catalog.problems))
    target = normalize_tag(locale) or catalog.canonical_locale
    functions = [_function_document(record, target, catalog) for record in load_all_functions()]
    guide_strings = {key: _localized(catalog, key, target) for key in GUIDE_KEYS}
    fallback_rows = [
        {"key": key, "locale": value["resolved_locale"]}
        for key, value in guide_strings.items()
        if value["fallback"]
    ]
    for function in functions:
        for field in (
            "title",
            "short_description",
            "purpose",
            "effects",
            "source_availability_label",
            "command_review_label",
            "persistence_label",
        ):
            value = function.get(field)
            if isinstance(value, dict) and value.get("fallback"):
                fallback_rows.append(
                    {
                        "function_id": function["function_id"],
                        "key": value["key"],
                        "locale": value["resolved_locale"],
                    }
                )
        for command in function["commands"]:
            for field in ("label", "usage", "explanation", "purpose", "scope_label"):
                value = command.get(field)
                if isinstance(value, dict) and value.get("fallback"):
                    fallback_rows.append(
                        {
                            "function_id": function["function_id"],
                            "command_id": command["id"],
                            "key": value["key"],
                            "locale": value["resolved_locale"],
                        }
                    )
            for relation in command["related_commands"]:
                value = relation["label"]
                if value.get("fallback"):
                    fallback_rows.append(
                        {
                            "function_id": function["function_id"],
                            "command_id": command["id"],
                            "key": value["key"],
                            "locale": value["resolved_locale"],
                        }
                    )
            for step in command["procedure_steps"]:
                value = step["instruction"]
                if value.get("fallback"):
                    fallback_rows.append(
                        {
                            "function_id": function["function_id"],
                            "command_id": command["id"],
                            "key": value["key"],
                            "locale": value["resolved_locale"],
                        }
                    )
    command_count = sum(len(function["commands"]) for function in functions)
    return {
        "schema_version": "1.0",
        "generated": True,
        "locale": target,
        "canonical_locale": catalog.canonical_locale,
        "guide_strings": guide_strings,
        "function_count": len(functions),
        "command_count": command_count,
        "fallback_count": len(fallback_rows),
        "fallbacks": fallback_rows,
        "functions": functions,
    }


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_command_index(index: dict) -> str:
    functions = index["functions"]
    note = ""
    if index["fallback_count"]:
        fallback_note = _localized_from_index(index, "command.guide.fallback-note")
        note = f"\n> {fallback_note}\n"
    rows = []
    for function in functions:
        for command in function["commands"]:
            if not command.get("documentation", {}).get("visible", True):
                continue
            rows.append(
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        f"[{function['title']['text']}](functions/{function['function_id']}.md)",
                        command["phrase"],
                        command["label"]["text"],
                        command["usage"]["text"],
                        command["scope_label"]["text"],
                    )
                )
                + " |"
            )
    if not functions:
        raise CommandDocumentationError("cannot render a command index with no functions")
    headings = [
        _localized_from_index(index, key)
        for key in (
            "command.guide.function",
            "command.guide.phrase",
            "command.guide.role",
            "command.guide.usage",
            "command.guide.scope",
        )
    ]
    table = "\n".join(
        ["| " + " | ".join(headings) + " |", "| --- | --- | --- | --- | --- |", *rows]
    )
    canonical_note = _localized_from_index(index, "command.guide.canonical-note")
    return (
        f"# {_markdown_cell(_localized_from_index(index, 'command.guide.index-title'))}\n\n"
        f"{_markdown_cell(canonical_note)}\n"
        f"{note}\n{table}\n\n"
        f"{index['function_count']} {_localized_from_index(index, 'command.guide.function-count')}; "
        f"{index['command_count']} {_localized_from_index(index, 'command.guide.command-count')}.\n"
    )


def _localized_from_index(index: dict, key: str) -> str:
    """Resolve a shared guide label from the localized index bundle."""
    try:
        return index["guide_strings"][key]["text"]
    except KeyError as exc:
        raise CommandDocumentationError(f"command guide UI key {key!r} is unavailable") from exc


def render_function_sheet(function: dict, index: dict) -> str:
    strings = index["guide_strings"]
    description_lines = []
    if function["short_description"]["text"] != function["purpose"]["text"]:
        description_lines.extend(
            [
                f"**{strings['command.guide.summary']['text']}**: {function['short_description']['text']}",
                "",
            ]
        )
    description_lines.extend(
        [
            f"**{strings['command.guide.purpose']['text']}**: {function['purpose']['text']}",
            "",
        ]
    )
    lines = [
        f"# {function['title']['text']}",
        "",
        *description_lines,
        f"**{strings['command.guide.scope']['text']}**: {function['persistence_label']['text']} (`{function['persistence']}`)",
        "",
        f"**{strings['command.guide.source-status']['text']}**: {function['source_availability_label']['text']} (`{function['source_availability']}`)",
        "",
        strings["command.guide.source-auth-note"]["text"],
        "",
        f"**{strings['command.guide.command-review']['text']}**: {function['command_review_label']['text']} (`{function['canonical_command_review']}`)",
        "",
        "[Command index](../COMMAND_INDEX.md)",
        "",
    ]
    if function.get("effects"):
        lines.extend(
            [
                f"**{strings['command.guide.effects']['text']}**: {function['effects']['text']}",
                "",
            ]
        )
    for command in function["commands"]:
        if not command.get("documentation", {}).get("visible", True):
            continue
        lines.extend(
            [
                f"## {command['phrase']}",
                "",
                f"**{command['label']['text']}**",
                "",
                command["usage"]["text"],
                "",
                command["explanation"]["text"],
                "",
            ]
        )
        if command.get("observed_phrase"):
            observed = command["observed_phrase"]
            lines.extend(
                [
                    f"**{strings['command.guide.observed']['text']}**: {observed['text']} `({observed['relationship']}; {observed['narration_key']})`",
                    "",
                ]
            )
        if command.get("procedure_steps"):
            role_key = f"command.procedure-heading.{command['role']}"
            heading = strings.get(role_key)
            if heading is None:
                raise CommandDocumentationError(f"command guide UI key {role_key!r} is unavailable")
            lines.append(f"**{heading['text']}**")
            lines.extend(
                f"{index_step}. {step['instruction']['text']}"
                for index_step, step in enumerate(command["procedure_steps"], start=1)
            )
            lines.append("")
        elif command.get("role") != "legacy-alias":
            lines.extend(
                [
                    f"**{strings['command.guide.procedure']['text']}**: {strings['command.guide.no-procedure']['text']}",
                    "",
                ]
            )
        relation_rows = command.get("related_commands", [])
        if relation_rows:
            lines.append(f"**{strings['command.guide.relationships']['text']}**")
            for relation in relation_rows:
                targets = ", ".join(f"`{item['phrase']}`" for item in relation["commands"])
                lines.append(f"- {relation['label']['text']}: {targets}")
            lines.append("")
    fallback_count = index["fallback_count"]
    if fallback_count:
        lines.extend([f"> {strings['command.guide.fallback-note']['text']}", ""])
    lines.append(f"{strings['command.guide.canonical-note']['text']}")
    return "\n".join(lines).rstrip() + "\n"


def render_quick_reference(index: dict) -> str:
    rows = []
    for function in index["functions"]:
        visible = [
            command
            for command in function["commands"]
            if command.get("documentation", {}).get("visible", True)
            and command["role"] != "legacy-alias"
        ]
        primary = next(
            (command for command in visible if command["designation"] == "primary"), None
        )
        if primary:
            modes = "; ".join(
                f"{command['label']['text']}: {command['phrase']}"
                for command in visible
                if command is not primary
            )
            rows.append(
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        f"[{function['title']['text']}](functions/{function['function_id']}.md)",
                        primary["phrase"],
                        modes,
                        function["persistence_label"]["text"],
                        function["short_description"]["text"],
                    )
                )
                + " |"
            )
    table = "\n".join(
        [
            "| "
            + " | ".join(
                _localized_from_index(index, key)
                for key in (
                    "command.guide.function",
                    "command.guide.phrase",
                    "command.guide.other-commands",
                    "command.guide.scope",
                    "command.guide.summary",
                )
            )
            + " |",
            "| --- | --- | --- | --- | --- |",
            *rows,
        ]
    )
    return (
        f"# {_localized_from_index(index, 'command.guide.quick-title')}\n\n"
        f"{_localized_from_index(index, 'command.guide.canonical-note')}\n\n{table}\n"
    )


def generated_command_documents() -> list[tuple[str, str]]:
    """Generate all checked-in command reference views in canonical en-US."""
    index = build_command_index("en-US")
    outputs = [
        ("docs/COMMAND_INDEX.md", render_command_index(index)),
        ("docs/COMMAND_QUICK_REFERENCE.md", render_quick_reference(index)),
        (
            "function-command-index.json",
            json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        ),
    ]
    outputs.extend(
        (
            f"docs/functions/{function['function_id']}.md",
            render_function_sheet(function, index),
        )
        for function in index["functions"]
    )
    return [
        (
            path,
            text if path == "function-command-index.json" else generated_content(text),
        )
        for path, text in outputs
    ]


def run_cli(args: Any) -> int:
    """CLI for localized command listing, function references, and export."""
    if args.command_kind == "list":
        index = build_command_index(args.locale)
        if args.json:
            print(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            for function in index["functions"]:
                visible = [
                    command
                    for command in function["commands"]
                    if command.get("documentation", {}).get("visible", True)
                ]
                if getattr(args, "all_roles", False):
                    for command in visible:
                        role_text = command.get("label", {}).get("text", command["role"])
                        print(f"{function['function_id']}: {function['title']['text']} — {command['phrase']} [{role_text}]")
                else:
                    primary = next(
                        (
                            command["phrase"]
                            for command in visible
                            if command["designation"] == "primary"
                        ),
                        "(no primary command)",
                    )
                    print(f"{function['function_id']}: {function['title']['text']} — {primary}")
        return 0
    if args.command_kind == "describe":
        from .indexes import load_function_by_slug_or_id

        record = load_function_by_slug_or_id(args.function)
        if record is None:
            raise OCFError(f"unknown function {args.function}; use `ocf commands list`")
        index = build_command_index(args.locale)
        function = next(item for item in index["functions"] if item["function_id"] == record.id)
        if args.json:
            print(json.dumps(function, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(render_function_sheet(function, index), end="")
        return 0
    if args.command_kind == "export":
        index = build_command_index(args.locale)
        text = (
            json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
            if args.format == "json"
            else render_command_index(index)
        )
        if args.output:
            output = Path(args.output).expanduser()
            write_text_atomic(output, text, overwrite=args.force)
        else:
            print(text, end="")
        return 0
    raise OCFError(f"unknown commands action: {args.command_kind}")
