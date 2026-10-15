"""Deterministic compact source plans; composition remains the single timing API."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .audio_defaults import LOCK_PATH, check_lock
from .complete_session import _slot_keys, build_complete_session_plan
from .content import CONTENT_DIR, load_layers
from .indexes import load_all_functions
from .locale import LocaleCatalog, normalize_tag
from .paths import REPO_ROOT
from .session import load_template
from .utils import OCFError, sha256_of_file, write_text_atomic
from .validators import _load_schema, validate_against_schema

PLAN_DIR = REPO_ROOT / "audio" / "session-plans"
GENERATOR = "ocf.audio.plan/1"


def serialize(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def digest(value: dict) -> str:
    return hashlib.sha256(serialize(value).encode("utf-8")).hexdigest()


def source_plan(function_id: str, locale: str = "en-US") -> tuple[dict, dict, dict]:
    lock = check_lock()
    expanded = build_complete_session_plan(function_id, locale=locale)
    binding = load_layers(function_id)["bindings"]
    template = load_template(expanded["template"]["id"])
    slots = _slot_keys(binding, template)
    if template["id"] != lock["profiles"]["template"]["id"]:
        raise OCFError(
            f"{function_id}: custom template requires a separately versioned defaults lock"
        )
    catalog = LocaleCatalog()
    resources = {}
    for item in expanded["narration_resources"]:
        entry, resolution = catalog.resource(
            item["key"], locale, domain="narration", fallback=False
        )
        resources[item["key"]] = {
            "key": item["key"],
            "locale": resolution.origin_locale,
            "requested_locale": resolution.locale,
            "fallback": resolution.fallback,
            "version": entry.version,
            "status": entry.status,
            "text_sha256": hashlib.sha256(entry.text.encode("utf-8")).hexdigest(),
        }
    shared = {
        "schema_version": "1.0",
        "generator": GENERATOR,
        "defaults_lock": LOCK_PATH.relative_to(REPO_ROOT).as_posix(),
        "defaults_sha256": digest(lock),
        "profiles": lock["profiles"],
        "timing": {
            "anchor_basis": "measured-speech-end/event-end",
            "fixed_speech_timestamps": False,
            "body_repetitions": {"programming": 2, "sleep": 2},
        },
        "resources": [resources[k] for k in sorted(resources) if k not in slots.values()],
    }
    plan = {
        "schema_version": "1.0",
        "generator": GENERATOR,
        "function_id": function_id,
        "locale": expanded["locale"],
        "defaults": {"file": "_shared.json", "sha256": digest(shared)},
        "slots": slots,
        "resources": [resources[k] for k in sorted(resources) if k in slots.values()],
        "timing": "measured-speech-relative; expand template at render time",
        "generation": {
            "binding_sha256": sha256_of_file(CONTENT_DIR / "bindings" / f"{function_id}.yaml"),
            "semantic_plan_sha256": digest(expanded["template_plan"]),
        },
        "approval": {
            "human_review": expanded["approval_state"]["function_review_status"],
            "release_ready": False,
        },
    }
    errors = validate_against_schema(plan, _load_schema("session-plan.schema.json"))
    if errors:
        raise OCFError("invalid generated session declaration: " + " | ".join(errors))
    return plan, shared, expanded


def generate_plans(
    function_ids: list[str] | None = None,
    *,
    locale: str = "en-US",
    output: Path | None = None,
    check: bool = False,
    dry_run: bool = False,
) -> dict:
    locale = normalize_tag(locale)
    if not locale:
        raise OCFError("invalid locale")
    ids = sorted(
        set(function_ids if function_ids is not None else [r.id for r in load_all_functions()])
    )
    if not ids:
        raise OCFError("no functions selected")
    root = (output or PLAN_DIR) / locale
    files = {}
    errors = {}
    for owner in ids:
        try:
            plan, shared, _ = source_plan(owner, locale)
            shared_text = serialize(shared)
            if "_shared.json" in files and files["_shared.json"] != shared_text:
                raise OCFError("selected functions have conflicting shared defaults")
            files["_shared.json"] = shared_text
            files[f"{owner}.json"] = serialize(plan)
        except OCFError as exc:
            errors[owner] = str(exc)
    if errors:
        raise OCFError("session planning failed: " + serialize(errors))
    stale = [
        name
        for name, text in files.items()
        if not (root / name).is_file() or (root / name).read_text(encoding="utf-8") != text
    ]
    unexpected = (
        sorted(p.name for p in root.glob("*.json") if p.name not in files)
        if function_ids is None
        else []
    )
    if check and (stale or unexpected):
        raise OCFError("session plans are stale: " + ", ".join(sorted(set(stale + unexpected))))
    if not check and not dry_run:
        for name in files:
            path = root / name
            if path.exists():
                try:
                    owned = (
                        json.loads(path.read_text(encoding="utf-8")).get("generator") == GENERATOR
                    )
                except (ValueError, AttributeError):
                    owned = False
                if not owned:
                    raise OCFError(f"refusing to replace manually maintained plan {path}")
        for name, text in files.items():
            write_text_atomic(root / name, text)
    return {
        "total": len(ids),
        "validated": len(ids),
        "locale": locale,
        "functions": ids,
        "dry_run": dry_run,
        "check": check,
        "stale": stale,
        "files": {
            name: hashlib.sha256(text.encode("utf-8")).hexdigest()
            for name, text in sorted(files.items())
        },
    }
