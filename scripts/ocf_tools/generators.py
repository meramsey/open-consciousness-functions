"""Generation of all derived indexes and matrices from the YAML records.

Everything produced here must remain deterministic so that ``build-index
--check`` can fail cleanly when records drift from their derived files.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .indexes import (
    audio_implementations_for,
    background_presets_for,
    load_all_functions,
    load_audio_manifests,
    load_background_manifests,
)
from .models import FunctionRecord
from .paths import DOCS_DIR, LEGACY_DIR, REPO_ROOT, ensure_dir
from .utils import generated_content, write_text_atomic

INDEX_COLUMNS = [
    "ocf_id",
    "canonical_name",
    "legacy_name",
    "canonical_command",
    "legacy_command",
    "domains",
    "persistence",
    "source_availability",
    "reimplementation_status",
    "command_review",
    "compatibility",
    "audio_impl_count",
    "background_preset_count",
    "source_file",
]


def row_for(record: FunctionRecord) -> dict[str, Any]:
    """Build one index row for a function record."""
    legacy_commands = " / ".join(record.legacy_commands) or ""
    domains = ";".join([record.primary_domain] + record.secondary_domains)
    audio_count = len(audio_implementations_for(record.id))
    background_count = len(background_presets_for(record.id))
    relative_path = record.path.relative_to(REPO_ROOT).as_posix()
    return {
        "ocf_id": record.id,
        "canonical_name": record.canonical_name,
        "legacy_name": record.legacy_name,
        "canonical_command": record.canonical_command or "",
        "legacy_command": legacy_commands,
        "domains": domains,
        "persistence": record.persistence,
        "source_availability": record.source_availability,
        "reimplementation_status": record.reimplementation_status,
        "command_review": record.command_review,
        "compatibility": record.compatibility,
        "audio_impl_count": audio_count,
        "background_preset_count": background_count,
        "source_file": relative_path,
    }


def build_function_index_data() -> list[dict[str, Any]]:
    """Sorted list of index rows."""
    return [row_for(record) for record in load_all_functions()]


# --------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    out: list[str] = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out) + "\n"


def function_index_markdown() -> str:
    headers = [
        "OCF ID",
        "Canonical name",
        "Legacy name",
        "Canonical command",
        "Legacy command",
        "Domains",
        "Persistence",
        "Source",
        "OCF reimpl.",
        "Command review",
        "Compat",
        "Audio",
        "BG",
        "File",
    ]
    rows: list[list[str]] = []
    for record in load_all_functions():
        rows.append(
            [
                f"`{record.id}`",
                record.canonical_name,
                record.legacy_name,
                f"`{record.canonical_command or ''}`",
                " / ".join(f"`{c}`" for c in record.legacy_commands),
                record.primary_domain,
                record.persistence,
                record.source_availability,
                record.reimplementation_status,
                record.command_review,
                record.compatibility,
                str(len(audio_implementations_for(record.id))),
                str(len(background_presets_for(record.id))),
                record.path.relative_to(REPO_ROOT).as_posix(),
            ]
        )
    body = "\n".join(
        [
            "# Function Index",
            "",
            "Complete index of every OCF function record. Sorted by OCF ID.",
            "",
            _markdown_table(headers, rows),
            f"\n{len(rows)} functions listed.",
            "",
        ]
    )
    return generated_content(body)


def function_index_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=INDEX_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in build_function_index_data():
        writer.writerow(row)
    return generated_content(buffer.getvalue())


def function_index_json() -> str:
    payload = {
        "generated": True,
        "count": len(build_function_index_data()),
        "functions": build_function_index_data(),
    }
    return generated_content(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def hplus_command_map_json() -> str:
    payload = {"source_system": "Monroe H-PLUS", "count": 0, "mappings": []}
    for record in load_all_functions():
        entry = {
            "legacy_name": record.legacy_name,
            "legacy_commands": record.legacy_commands,
            "ocf_id": record.id,
            "canonical_name": record.canonical_name,
            "canonical_commands": [record.canonical_command or ""] + record.command_modes,
            "command_status": record.command_status,
            "command_review": record.command_review,
            "compatibility": record.compatibility,
            "source_availability": record.source_availability,
            "reimplementation_status": record.reimplementation_status,
        }
        payload["mappings"].append(entry)
    payload["count"] = len(payload["mappings"])
    return generated_content(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def hplus_command_map_csv() -> str:
    headers = [
        "legacy_name",
        "legacy_command",
        "ocf_id",
        "canonical_command",
        "command_status",
        "command_review",
        "compatibility",
        "source_availability",
        "reimplementation_status",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for record in load_all_functions():
        writer.writerow(
            {
                "legacy_name": record.legacy_name,
                "legacy_command": " / ".join(record.legacy_commands),
                "ocf_id": record.id,
                "canonical_command": record.canonical_command or "",
                "command_status": record.command_status,
                "command_review": record.command_review,
                "compatibility": record.compatibility,
                "source_availability": record.source_availability,
                "reimplementation_status": record.reimplementation_status,
            }
        )
    return generated_content(buffer.getvalue())


def command_review_markdown() -> str:
    records = load_all_functions()
    unchanged = sorted([r for r in records if r.command_status == "unchanged"], key=lambda r: r.id)
    normalized = sorted(
        [r for r in records if r.command_status == "normalized"], key=lambda r: r.id
    )
    proposed = sorted(
        [r for r in records if r.command_status in ("proposed", "review-required")],
        key=lambda r: r.id,
    )

    def table_for(items: list[FunctionRecord]) -> str:
        rows = []
        for record in items:
            rows.append(
                [
                    f"`{record.id}`",
                    record.legacy_name,
                    " / ".join(f"`{c}`" for c in record.legacy_commands),
                    f"`{record.canonical_command or ''}`",
                    " / ".join(f"`{m}`" for m in record.command_modes),
                    record.command_review,
                    record.compatibility,
                ]
            )
        return _markdown_table(
            ["OCF ID", "Legacy name", "Legacy command", "Canonical", "Modes", "Review", "Compat"],
            rows,
        )

    body = "\n".join(
        [
            "# Command Review Report",
            "",
            "Command-design review generated from the canonical function records.",
            "",
            f"{len(records)} functions total.",
            "",
            "## Commands retained unchanged",
            "",
            f"{len(unchanged)} commands are unchanged:",
            "",
            table_for(unchanged),
            "",
            "## Commands normalized (proposed vocabulary)",
            "",
            "Adjustable-magnitude commands are normalized to the MORE/LESS grammar `N`.",
            "",
            f"{len(normalized)} commands normalized:",
            "",
            table_for(normalized),
            "",
            "## Commands still requiring review",
            "",
            "These commands have a proposed canonical form that has not been approved. "
            "Legacy commands are always retained as aliases/metadata.",
            "",
            f"{len(proposed)} commands requiring review:",
            "",
            table_for(proposed),
            "",
            "Review guidance: `docs/COMMAND_GRAMMAR.md` and `docs/NAMING_GUIDELINES.md`.",
            "",
        ]
    )
    return generated_content(body)


def availability_matrix_markdown() -> str:
    headers = ["OCF ID", "Legacy name", "Source availability", "OCF reimpl.", "Status"]
    rows = []
    available = sorted(
        [r for r in load_all_functions() if r.source_availability == "available"],
        key=lambda r: r.id,
    )
    unavailable = sorted(
        [r for r in load_all_functions() if r.source_availability == "unavailable"],
        key=lambda r: r.id,
    )
    for record in available:
        rows.append(
            [
                f"`{record.id}`",
                record.legacy_name,
                "available",
                record.reimplementation_status,
                record.maturity,
            ]
        )
    for record in unavailable:
        rows.append(
            [
                f"`{record.id}`",
                record.legacy_name,
                "unavailable",
                record.reimplementation_status,
                record.maturity,
            ]
        )
    body = "\n".join(
        [
            "# Availability Matrix",
            "",
            "Legacy source availability for every function. The 16 source-unavailable "
            "functions remain full OCF reimplementation targets (`planned`).",
            "",
            f"Available: {len(available)}  \\",
            f"Source unavailable: {len(unavailable)}",
            "",
            _markdown_table(headers, rows),
            "",
        ]
    )
    return generated_content(body)


def reimplementation_roadmap_markdown() -> str:
    planned = sorted(
        [r for r in load_all_functions() if r.reimplementation_status == "planned"],
        key=lambda r: r.id,
    )
    rows = []
    for record in planned:
        rows.append(
            [
                f"`{record.id}`",
                record.canonical_name,
                record.legacy_name,
                record.source_availability,
                "available" if record.source_availability == "available" else "proposal pathway",
            ]
        )
    body = "\n".join(
        [
            "# Reimplementation Roadmap",
            "",
            "Every function either has source material available (`available`) or is a "
            "full OCF reimplementation target with a community proposal pathway.",
            "",
            _markdown_table(
                ["OCF ID", "Canonical name", "Legacy name", "Source", "Pathway"],
                rows,
            ),
            "",
            f"{len(planned)} functions currently marked as OCF reimplementation targets.",
            "",
        ]
    )
    return generated_content(body)


def safety_matrix_markdown() -> str:
    headers = ["OCF ID", "Legacy name", "Safety level", "Medical relevance", "Notes"]
    rows = []
    for record in load_all_functions():
        credits = record.data.get("safety", {})
        rows.append(
            [
                f"`{record.id}`",
                record.legacy_name,
                record.safety_level,
                "yes" if credits.get("medical_relevance") else "",
                "; ".join(record.safety_notes),
            ]
        )
    body = "\n".join(
        [
            "# Safety Matrix",
            "",
            "Safety classification of every function. Health and emergency functions "
            "carry explicit statements; see `docs/SAFETY_POLICY.md`.",
            "",
            _markdown_table(headers, rows),
            "",
        ]
    )
    return generated_content(body)


def audio_implementation_index_markdown() -> str:
    manifests = load_audio_manifests()
    headers = ["Audio ID", "Function", "Title", "Type", "Language", "Status", "Link"]
    rows = []
    for manifest in sorted(manifests, key=lambda m: str(m.get("id", ""))):
        rows.append(
            [
                f"`{manifest.get('id')}`",
                f"`{manifest.get('function_id')}`",
                str(manifest.get("title", "")),
                str(manifest.get("training_type", "")),
                str(manifest.get("language", "")),
                str(manifest.get("review_state", "")),
                "",
            ]
        )
    body = "\n".join(
        [
            "# Audio Implementation Index",
            "",
            "Concrete audio implementations per function. Audio is optional for every "
            "function; a function may have several implementations.",
            "",
            _markdown_table(headers, rows),
            "",
            f"{len(rows)} audio implementations recorded.",
            "",
        ]
    )
    return generated_content(body)


def background_audio_index_markdown() -> str:
    manifests = load_background_manifests()
    headers = ["BG ID", "Name", "Engine", "Seed", "Deterministic", "Functions"]
    rows = []
    for manifest in sorted(manifests, key=lambda m: str(m.get("id", ""))):
        render = manifest.get("render", {})
        usage = manifest.get("usage", {})
        rows.append(
            [
                f"`{manifest.get('id')}`",
                str(manifest.get("name", "")),
                str(manifest.get("engine", "")),
                str(render.get("seed") or ""),
                "yes" if render.get("deterministic") else "no",
                ", ".join(usage.get("functions", [])),
            ]
        )
    body = "\n".join(
        [
            "# Background Audio Index",
            "",
            "Optional background presets. A preset is not a function and is not a "
            "training script; see `docs/BACKGROUND_AUDIO.md`.",
            "",
            _markdown_table(headers, rows),
            "",
            f"{len(rows)} background presets recorded.",
            "",
        ]
    )
    return generated_content(body)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def generate_all_content() -> list[tuple[str, str]]:
    """Return [(relative_path, content)] for every derived file."""
    return [
        ("FUNCTION_INDEX.md", function_index_markdown()),
        ("function-index.json", function_index_json()),
        ("function-index.csv", function_index_csv()),
        ("legacy/hplus-command-map.json", hplus_command_map_json()),
        ("legacy/hplus-command-map.csv", hplus_command_map_csv()),
        ("docs/COMMAND_REVIEW.md", command_review_markdown()),
        ("docs/AVAILABILITY_MATRIX.md", availability_matrix_markdown()),
        ("docs/REIMPLEMENTATION_ROADMAP.md", reimplementation_roadmap_markdown()),
        ("docs/SAFETY_MATRIX.md", safety_matrix_markdown()),
        ("docs/AUDIO_IMPLEMENTATION_INDEX.md", audio_implementation_index_markdown()),
        ("docs/BACKGROUND_AUDIO_INDEX.md", background_audio_index_markdown()),
    ]


def build_all_generated_files() -> list[Path]:
    """Write every generated file and return the list of paths written."""
    ensure_dir(DOCS_DIR)
    ensure_dir(LEGACY_DIR)
    written: list[Path] = []
    for relative, content in generate_all_content():
        target = REPO_ROOT / relative
        write_text_atomic(target, content)
        written.append(target)
    return written


def refresh_indexes() -> None:
    """Regenerate all derived files (used by `build-index`)."""
    build_all_generated_files()


def indexes_are_fresh() -> bool:
    """Return True when every generated file on disk matches regeneration."""
    for relative, content in generate_all_content():
        target = REPO_ROOT / relative
        if not target.exists():
            return False
        if target.read_text(encoding="utf-8") != content:
            return False
    return True
