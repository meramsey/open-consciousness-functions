"""Explicit binding migration and derived TTS eligibility, independent of sources."""

from __future__ import annotations

from .audio_defaults import TEMPLATE_ID
from .content import CONTENT_DIR, load_layers
from .indexes import load_all_functions, load_function_by_id
from .locale import LocaleCatalog
from .utils import OCFError, write_text_atomic, yaml_safe_dump


def migrate_bindings(function_ids: list[str], *, dry_run: bool = True) -> list[dict]:
    """Deliberate migration: fill missing plans; retain existing manual sequences.

    Only the known standard default is upgraded. Custom defaults are preserved.
    Resource identity follows the same stable-ID contract as session compose.
    All candidate bindings resolve successfully before any write occurs.
    """
    catalog = LocaleCatalog()
    pending = []
    for owner in sorted(set(function_ids)):
        if load_function_by_id(owner) is None:
            raise OCFError(f"unknown function {owner}")
        layers = load_layers(owner)
        binding = layers.get("bindings")
        if binding is None:
            binding = {
                "schema_version": "1.0",
                "function_id": owner,
                "session_templates": [],
                "narration_resources": [],
                "voice_sources": ["tts"],
                "duration": None,
            }
        if not binding.get("narration_plan"):
            sequence = []
            for role in ("opener", "function-body", "closer"):
                key = f"hplus.function.{owner.lower()}.{role}"
                entry, _ = catalog.resource(key, "en-US", domain="narration", fallback=False)
                if not entry.text.strip():
                    raise OCFError(f"empty required narration: {key}")
                sequence.append(
                    {"key": key, "role": role, "repetitions": 4 if role == "function-body" else 1}
                )
            binding["narration_plan"] = {"sequence": sequence}
        if binding.get("default_session_template") in (None, "OCF-TPL-SESSION-HPLUS-STANDARD-001"):
            binding["default_session_template"] = TEMPLATE_ID
            binding["session_templates"] = sorted(set(binding["session_templates"]) | {TEMPLATE_ID})
        binding["voice_sources"] = sorted(set(binding.get("voice_sources") or []) | {"tts"})
        from .content import validate_layers

        errors = validate_layers({"bindings": binding}, owner)
        if errors:
            raise OCFError(" | ".join(errors))
        pending.append((CONTENT_DIR / "bindings" / f"{owner}.yaml", binding))
    if not dry_run:
        for path, binding in pending:
            write_text_atomic(path, yaml_safe_dump(binding))
    return [
        {
            "function_id": binding["function_id"],
            "default_session_template": binding.get("default_session_template"),
            "dry_run": dry_run,
        }
        for _, binding in pending
    ]


def eligibility(function_id: str, locale: str = "en-US") -> dict:
    """Compute capability; never promote editorial, source or release status."""
    from .complete_session import build_complete_session_plan

    record = load_function_by_id(function_id)
    result = {
        "function_id": function_id,
        "locale": locale,
        "function_exists": record is not None,
        "historical_source_availability": record.source_availability if record else None,
        "narration_complete": False,
        "narration_review_status": {},
        "tts_renderable": False,
        "timing_plan_available": False,
        "audio_rendered": None,
        "release_ready": False,
        "audio_rendered_basis": "unknown until a local render manifest is verified",
        "human_review": "unknown",
        "blockers": [],
    }
    try:
        plan = build_complete_session_plan(function_id, locale=locale)
        result.update(narration_complete=True, tts_renderable=True, timing_plan_available=True)
        result["human_review"] = plan["approval_state"]["function_review_status"]
        result["narration_review_status"] = {
            r["key"]: r["status"] for r in plan["narration_resources"]
        }
    except (OCFError, ValueError) as exc:
        result["blockers"].append(str(exc))
    return result


def migration_report(locale: str = "en-US") -> dict:
    rows = [eligibility(r.id, locale) for r in load_all_functions()]
    return {
        "schema_version": "1.0",
        "locale": locale,
        "total": len(rows),
        "previous_source_available": sum(
            r["historical_source_availability"] == "available" for r in rows
        ),
        "previous_source_unavailable": sum(
            r["historical_source_availability"] == "unavailable" for r in rows
        ),
        "tts_renderable": sum(r["tts_renderable"] for r in rows),
        "functions": rows,
    }
