"""Bounded multi-function review, using actual bindings and exact sentence excerpts."""

from __future__ import annotations

import json

from .complete_session import build_complete_session_plan
from .indexes import load_function_by_id
from .locale import LocaleCatalog, iter_events, resolve_document
from .narration_pacing import split_speech_units
from .paths import unique_run_id, work_path
from .speech_cache import enabled
from .utils import OCFError, sha256_of_file, write_text_atomic
from .voice import render_narration


def review_sessions(
    function_ids: list[str], *, locale: str = "en-US", voice: str | None = None
) -> dict:
    if not function_ids or len(set(function_ids)) > 8:
        raise OCFError("select 1..8 representative functions; bulk full rendering is separate")
    rows = []
    root = work_path("renders", unique_run_id("category-review")) if voice else None
    for owner in sorted(set(function_ids)):
        plan = build_complete_session_plan(owner, locale=locale)
        record = load_function_by_id(owner)
        doc = resolve_document(plan["template_plan"], locale, strict=True)
        events = list(iter_events(doc))
        body = [e for e in events if e.get("slot_ref") == "function_body"]
        row = {
            "function_id": owner,
            "title": record.canonical_name,
            "category": record.data["classification"]["primary_domain"],
            "template": plan["template"],
            "body_passes": len(body),
            "stage_order": [s["id"] for s in plan["stages"]],
            "dsp": plan["dsp_profile"],
            "transitions": plan["effective_state_directives"],
            "waking_return": any(e.get("semantic") == "session.return.complete" for e in events),
            "sleep_passes": len(
                next((s["event_ids"] for s in plan["stages"] if s["id"] == "sleep20-body"), [])
            ),
            "pacing_events": len(plan["narration_pacing_plan"]),
            "release_ready": False,
            "listening_approval": None,
        }
        if voice:
            catalog = LocaleCatalog()
            selected = []
            for role in ("opener", "function-body", "closer"):
                resource = next(
                    r for r in plan["tts_plan"]["narration_resources"] if r["role"] == role
                )
                entry, resolution = catalog.resource(
                    resource["key"], locale, domain="narration", fallback=False
                )
                # Excerpt boundaries select whole authored sentences; no rewriting.
                text = " ".join(u["text"] for u in split_speech_units(entry.text)[:2])
                selected.append(
                    {
                        "id": role,
                        "text": text,
                        "locale": resolution.origin_locale,
                        "timing": {"pause_after": 3, "anchor": "speech-end"},
                    }
                )
                if len(selected) == 1:
                    selected[-1]["at"] = "00:00.000"
                    selected[-1]["timing"]["anchor"] = "start"
                else:
                    selected[-1].update(after=selected[-2]["id"], offset=0)
            path = root / f"{owner}-review.wav"
            root.mkdir(parents=True, exist_ok=True)
            with enabled():
                result = render_narration(
                    {
                        "schema_version": "1.0",
                        "title": "Exact sentence review excerpt",
                        "locale": locale,
                        "timeline": selected,
                    },
                    path,
                    backend=voice,
                )
            row["excerpt"] = {
                "path": path.name,
                "duration_seconds": result["duration"],
                "sha256": sha256_of_file(path),
                "background": "none; speech review only",
            }
        rows.append(row)
    report = {
        "schema_version": "1.0",
        "locale": locale,
        "functions": rows,
        "policy": "Actual bound template governs repetitions/endings; category names never select a different ending.",
        "audio_verification": "speech excerpts only"
        if voice
        else "engine-independent structural validation",
    }
    if root:
        write_text_atomic(
            root / "comparison.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        report["output_directory"] = str(root)
    return report
