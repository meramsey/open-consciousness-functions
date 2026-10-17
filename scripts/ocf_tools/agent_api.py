"""Compact provider-neutral adapters; CLI/services remain authoritative."""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import re
import types
from dataclasses import asdict
from pathlib import Path, PureWindowsPath
from typing import get_args, get_origin, get_type_hints

from .paths import REPO_ROOT, SCHEMAS_DIR, work_root
from .utils import OCFError

MAX_PAGE = 50


def public(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        try:
            result = function(*args, **kwargs)
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 32768:
                return {
                    "status": "response-too-large",
                    "truncated": True,
                    "action": "Reduce page size, select fields or request summary mode; full artifacts remain local.",
                }
            return result
        except (OCFError, ValueError, TypeError, OSError, KeyError) as exc:
            return {
                "status": "failed",
                "code": "invalid-request-or-dependency",
                "message": str(exc).replace(str(REPO_ROOT), ".")[:1500],
                "action": "Check the selected IDs/arguments and the canonical CLI help.",
            }

    return call


def page(rows: list, offset: int = 0, limit: int = 10) -> dict:
    if not 0 <= offset or not 1 <= limit <= MAX_PAGE:
        raise OCFError(f"offset must be nonnegative; limit must be 1..{MAX_PAGE}")
    selected = rows[offset : offset + limit]
    return {
        "items": selected,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "truncated": offset + len(selected) < len(rows),
        "next_offset": offset + len(selected) if offset + len(selected) < len(rows) else None,
    }


def owner(function_id: str):
    from .indexes import load_function_by_id

    if not re.fullmatch(r"OCF-[A-Z]{3}-[0-9]{3}", function_id):
        raise OCFError("invalid function ID")
    record = load_function_by_id(function_id)
    if record is None:
        raise OCFError(f"unknown function {function_id}")
    return record


def safe_path(value: str, root: Path, *, exists: bool = True) -> Path:
    if (
        not value
        or any(ord(c) < 32 for c in value)
        or "\\" in value
        or PureWindowsPath(value).drive
        or PureWindowsPath(value).root
    ):
        raise OCFError("use a relative forward-slash path")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise OCFError("path must be relative and contained")
    path = (root / candidate).resolve()
    if not path.is_relative_to(root.resolve()) or (exists and not path.is_file()):
        raise OCFError("path is unavailable or outside the allowed root")
    return path


def workspace_manifest(manifest: str, *, dataset: bool = False) -> tuple[Path, dict]:
    """Bound private manifest reads before any resolver follows asset references."""
    import yaml

    from .utils import yaml_safe_load

    path = safe_path(manifest, work_root())
    if path.suffix.lower() not in ({".json"} if dataset else {".json", ".yaml", ".yml"}):
        raise OCFError("select a JSON dataset or JSON/YAML narration manifest")
    with path.open("rb") as handle:
        raw = handle.read(2 * 1024**2 + 1)
    if len(raw) > 2 * 1024**2:
        raise OCFError("manifest exceeds 2 MiB")
    try:
        data = (
            json.loads(raw)
            if path.suffix.lower() == ".json"
            else yaml_safe_load(raw.decode("utf-8"))
        )
    except yaml.YAMLError as exc:
        raise OCFError("invalid YAML manifest") from exc
    if not isinstance(data, dict):
        raise OCFError("manifest must contain an object")
    json.dumps(data, allow_nan=False)
    manifest_assets(path, data, dataset=dataset)
    return path, data


def manifest_assets(path: Path, data: dict, *, dataset: bool = False) -> dict[str, Path]:
    """Portable references, including unselected takes and future full-session stems."""
    references = {}
    if dataset:
        records = data.get("records", [])
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise OCFError("dataset records must be a list of objects")
        for index, row in enumerate(records):
            references[f"record:{index}"] = row["audio"]
        if data.get("consent_record"):
            references["consent_record"] = data["consent_record"]
    else:
        recordings = data.get("recordings", {})
        if not isinstance(recordings, dict) or any(
            not isinstance(row, dict) for row in recordings.values()
        ):
            raise OCFError("recordings must be an object of recording entries")
        for name, row in recordings.items():
            references[f"recording:{name}"] = row["file"]
        if data.get("session_stem") is not None:
            if not isinstance(data["session_stem"], dict):
                raise OCFError("session_stem must be an object")
            references["session_stem"] = data["session_stem"]["file"]
    assets = {}
    for name, value in references.items():
        if not isinstance(value, str):
            raise OCFError("asset reference must be a portable relative path")
        asset = safe_path(value, path.parent, exists=False)
        if asset.exists() and not asset.is_file():
            raise OCFError("asset reference must name a file")
        assets[name] = asset
    return assets


def compact_source_event(row: dict) -> dict:
    """Event identity/selection only; never return narration or arbitrary metadata."""
    keys = (
        "event_id",
        "narration_key",
        "stage_id",
        "source",
        "speaker",
        "voice",
        "selection_scope",
        "text_sha256",
        "text_compatibility",
        "fallback_reason",
        "recording_id",
        "gain_db",
        "rate_scale",
    )
    result = {key: row[key] for key in keys if key in row}
    if "recording" in row:
        result["recording"] = {
            key: row["recording"][key]
            for key in ("sha256", "version", "approval")
            if key in row["recording"]
        }
    if "units" in row:
        from collections import Counter

        result["units"] = {
            "total": len(row["units"]),
            "sources": dict(Counter(unit["source"] for unit in row["units"])),
        }
    return result


@public
def inspect_narration_sources(
    function_id: str, manifest: str, locale: str = "en-US", offset: int = 0, limit: int = 10
) -> dict:
    """Read-only source coverage with per-event pagination and no narration text."""
    from .locale import normalize_tag
    from .narration_cli import coverage

    owner(function_id)
    page([], offset, limit)
    path, _ = workspace_manifest(manifest)
    report = coverage(function_id, locale=normalize_tag(locale), sources=path)
    return {
        key: report[key]
        for key in (
            "schema_version",
            "id",
            "mode",
            "manifest_sha256",
            "locale",
            "fallback",
            "speakers",
            "speaker_consistency",
            "output_channels",
            "content_verification",
        )
        if key in report
    } | {
        "function_id": function_id,
        "events": page([compact_source_event(row) for row in report["events"]], offset, limit),
    }


@public
def validate_recordings(
    function_id: str, manifest: str, locale: str = "en-US", idempotency_key: str | None = None
) -> dict:
    """Explicit job: validate the whole source selection and measure selected originals."""
    from .dev_jobs import start

    return start(
        "narration-validate",
        {
            "function_id": function_id,
            "manifest": manifest,
            "locale": locale,
        },
        idempotency_key,
    )


@public
def start_narration_render(
    function_id: str,
    manifest: str,
    locale: str = "en-US",
    voice: str | None = None,
    pacing: str = "sleep",
    idempotency_key: str | None = None,
    mix_profile: str | None = None,
) -> dict:
    """Explicit recorded/hybrid complete-session job; unique workspace output."""
    from .dev_jobs import start

    return start(
        "narration-render",
        {
            "function_id": function_id,
            "manifest": manifest,
            "locale": locale,
            "voice": voice,
            "pacing": pacing,
            **({"mix_profile": mix_profile} if mix_profile is not None else {}),
        },
        idempotency_key,
    )


@public
def project_overview() -> dict:
    from .indexes import load_all_functions

    return {
        "project": "Open Consciousness Functions",
        "python": ">=3.11",
        "functions": len(load_all_functions()),
        "authority": "CLI, schemas, canonical YAML and application services",
        "guides": ["AGENTS.md", "docs/README.md", "docs/BULK_SESSIONS.md", "docs/MCP.md"],
        "workspace": ".ocf-work",
        "transport": "optional local stdio",
        "operations": sorted(TOOLS),
        "release_approval_inferred": False,
    }


@public
def list_functions(
    category: str | None = None,
    locale: str = "en-US",
    renderable: bool | None = None,
    approval: str | None = None,
    release_ready: bool | None = None,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    from .content import load_layers
    from .eligibility import eligibility
    from .indexes import load_all_functions
    from .locale import normalize_tag

    normalize_tag(locale)
    page([], offset, limit)
    rows = []
    for record in load_all_functions():
        domain = record.data["classification"]["primary_domain"]
        if category and domain != category:
            continue
        review = load_layers(record.id).get("specifications", {}).get("human_review", "unknown")
        if approval and review != approval:
            continue
        if release_ready is True:
            continue  # Planning/audition APIs never establish release clearance.
        row = {
            "id": record.id,
            "name": record.canonical_name,
            "category": domain,
            "human_review": review,
            "source_availability": record.source_availability,
        }
        if renderable is not None:
            eligible = eligibility(record.id, locale)["tts_renderable"]
            if eligible != renderable:
                continue
            row["tts_renderable"] = eligible
        rows.append(row)
    return page(rows, offset, limit)


@public
def get_function(
    function_id: str, fields: list[str] | None = None, previous_hash: str | None = None
) -> dict:
    from .commands import cue_presentation
    from .content import load_layers

    record = owner(function_id)
    layers = load_layers(function_id)
    data = {
        "id": record.id,
        "name": record.canonical_name,
        "commands": record.data["canonical"]["command"],
        "source_availability": record.source_availability,
        "human_review": layers.get("specifications", {}).get("human_review", "unknown"),
        "binding": layers.get("bindings", {}),
        "provenance": {
            "evidence_file": f"function-content/evidence/{record.id}.yaml",
            "source_count": len(layers.get("evidence", {}).get("sources", [])),
        },
        "release_ready": False,
        "cue_presentation": cue_presentation(record, "en-US"),
    }
    if fields:
        unknown = set(fields) - data.keys()
        if unknown:
            raise OCFError("unknown field(s): " + ", ".join(sorted(unknown)))
        data = {key: data[key] for key in sorted(set(fields) | {"id"})}
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return {
        "status": "unchanged" if previous_hash == fingerprint else "ok",
        "sha256": fingerprint,
        "data": None if previous_hash == fingerprint else data,
    }


@public
def get_schema(name: str, detail: bool = False) -> dict:
    if not re.fullmatch(r"[a-z0-9-]+\.schema\.json", name):
        raise OCFError("select a schema basename, e.g. function.schema.json")
    data = json.loads(safe_path(name, SCHEMAS_DIR).read_text(encoding="utf-8"))
    if detail:
        return {"schema": data}
    return {
        "name": name,
        "title": data.get("title"),
        "required": data.get("required", []),
        "fields": sorted(data.get("properties", {})),
        "artifact": f"schemas/{name}",
        "detail_available": True,
    }


@public
def get_workflow(name: str) -> dict:
    workflows = json.loads((REPO_ROOT / "docs/workflows.json").read_text(encoding="utf-8"))[
        "workflows"
    ]
    if name not in workflows:
        raise OCFError("unknown workflow; choose " + ", ".join(sorted(workflows)))
    return {"id": name, **workflows[name], "command_prefix": "python scripts/ocf.py"}


@public
def get_audio_defaults() -> dict:
    from .audio_defaults import LOCK_PATH, check_lock
    from .session_plans import digest

    lock = check_lock()
    return {key: value for key, value in lock.items() if key != "files"} | {
        "sha256": digest(lock),
        "locked_files": len(lock["files"]),
        "artifact": LOCK_PATH.relative_to(REPO_ROOT).as_posix(),
    }


@public
def get_session_plan(function_id: str, locale: str = "en-US", stages: bool = False) -> dict:
    from .session_plans import source_plan

    owner(function_id)
    compact, shared, expanded = source_plan(function_id, locale)
    result = {
        "function_id": function_id,
        "locale": compact["locale"],
        "slots": compact["slots"],
        "profiles": shared["profiles"],
        "timing": shared["timing"],
        "approval": compact["approval"],
        "voice_selection": expanded["voice_selection"],
        "sha256": compact["generation"]["semantic_plan_sha256"],
        "artifact": f"audio/session-plans/{compact['locale']}/{function_id}.json",
    }
    if stages:
        result["stages"] = expanded["stages"]
        result["dsp_transitions"] = expanded["effective_state_directives"]
    if expanded.get("resolved_overrides"):
        result["overrides"] = expanded["resolved_overrides"]
        result["override_provenance"] = expanded["override_provenance"]
        sections = {s["id"]: s for s in expanded["stages"]}
        result["timing"]["body_repetitions"] = {
            "programming": len(sections.get("focus11-body", {}).get("event_ids", [])),
            "sleep": len(sections.get("sleep20-body", {}).get("event_ids", [])),
        }
    return result


@public
def validate_function(
    function_id: str, categories: list[str] | None = None, offset: int = 0, limit: int = 20
) -> dict:
    from .content import load_layers
    from .eligibility import eligibility
    from .validators import (
        validate_command_metadata,
        validate_command_rules,
        validate_function_schema,
    )

    record = owner(function_id)
    categories = categories or ["schema", "commands", "narration"]
    if set(categories) - {"schema", "commands", "narration"}:
        raise OCFError("categories: schema, commands, narration")
    findings = []
    if "schema" in categories:
        findings.extend(asdict(i) for i in validate_function_schema(record).issues)
        load_layers(function_id)
    if "commands" in categories:
        findings.extend(asdict(i) for i in validate_command_rules(record).issues)
        findings.extend(asdict(i) for i in validate_command_metadata([record]).issues)
    if "narration" in categories:
        findings.extend(
            {
                "severity": "error",
                "code": "narration-dependency",
                "message": e,
                "target": function_id,
            }
            for e in eligibility(function_id)["blockers"]
        )
    errors = sum(i["severity"] == "error" for i in findings)
    warnings = sum(i["severity"] == "warning" for i in findings)
    result = page(findings, offset, limit)
    return {
        "status": "failed" if errors else "passed",
        "scope": [function_id],
        "errors": errors,
        "warnings": warnings,
        "diagnostics": result,
    }


@public
def validate_locale(locale: str = "en-US", offset: int = 0, limit: int = 20) -> dict:
    from .locale import LocaleCatalog, normalize_tag
    from .validators import validate_locale_packs

    tag = normalize_tag(locale)
    catalog = LocaleCatalog()
    if tag not in catalog.packs:
        raise OCFError(f"locale pack is not installed: {tag}")
    result = validate_locale_packs(catalog=catalog)
    rows = [asdict(i) for i in result.issues]
    return {
        "status": "passed" if result.ok else "failed",
        "scope": "all installed packs (cross-pack checks)",
        "requested_locale": tag,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
        "diagnostics": page(rows, offset, limit),
    }


@public
def validate_commands(function_id: str, offset: int = 0, limit: int = 20) -> dict:
    return validate_function(function_id, ["commands"], offset, limit)


@public
def final_validation() -> dict:
    """Start full repository validation; full pytest is a separate explicit job."""
    from .dev_jobs import start

    return start("validate", {})


@public
def select_tests(changed_files: list[str]) -> dict:
    tests = set()
    full = False
    mapping = {
        "voice.py": ["tests/test_voice_contracts.py", "tests/test_voice.py"],
        "speech_cache.py": ["tests/test_bulk_render.py"],
        "artifact_names.py": ["tests/test_artifact_names.py"],
    }
    for name in changed_files:
        safe_path(name, REPO_ROOT)
        if name.startswith("tests/") and name.endswith(".py"):
            tests.add(name)
        elif name.endswith(".md"):
            continue
        elif Path(name).name in mapping:
            tests.update(mapping[Path(name).name])
        else:
            full = True
    return {
        "tests": sorted(tests),
        "full_suite_required": full,
        "reason": "Shared/unknown implementation dependencies require explicit full-suite testing."
        if full
        else "Focused dependency map; final comprehensive gate remains required.",
        "documentation_checks": ["make lint"],
    }


@public
def plan_audio(function_id: str, voice: str, locale: str = "en-US", pacing: str = "sleep") -> dict:
    from .complete_session import render_complete_session
    from .diagnostics import diagnose

    owner(function_id)
    result = render_complete_session(
        function_id, voice=voice, locale=locale, pacing=pacing, dry_run=True
    )["session_plan"]
    tools = diagnose("farfield")
    return {
        "status": "ready" if tools["ok"] else "blocked",
        "dry_run": True,
        "function_id": function_id,
        "voice": result["voice"],
        "stage_count": len(result["stages"]),
        "function_narration_estimate_seconds": result["tts_plan"]["estimated_duration_seconds"],
        "estimate_basis": "function-specific word-rate estimate only; excludes shared narration/holds; not measured full-session duration or cost",
        "missing_dependencies": tools["failures"],
        "cache": "verified per segment/output at explicit start",
        "output_policy": ".ocf-work/renders/; unique non-overwriting audition",
        "requires_explicit_start": True,
    }


@public
def start_audio_render(
    function_id: str,
    voice: str,
    locale: str = "en-US",
    pacing: str = "sleep",
    force: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    from .dev_jobs import start

    preview = plan_audio(function_id, voice, locale, pacing)
    if preview.get("status") != "ready":
        return preview
    return start(
        "render",
        {
            "function_id": function_id,
            "voice": voice,
            "locale": locale,
            "pacing": pacing,
            "force": force,
        },
        idempotency_key,
    )


@public
def run_tests(
    paths: list[str] | None = None,
    full: bool = False,
    workers: int = 1,
    idempotency_key: str | None = None,
) -> dict:
    from .dev_jobs import start

    return start("tests", {"paths": paths or [], "full": full, "workers": workers}, idempotency_key)


@public
def check_generated(
    generate: bool = False, function_id: str | None = None, locale: str = "en-US"
) -> dict:
    from .dev_jobs import start

    if function_id:
        owner(function_id)
    return start("plans", {"function_id": function_id, "locale": locale, "generate": generate})


@public
def get_job_status(job_id: str) -> dict:
    from .dev_jobs import status

    return status(job_id)


@public
def get_job_result(job_id: str, offset: int = 0, limit: int = 20) -> dict:
    from .dev_jobs import job_result

    return job_result(job_id, offset=offset, limit=limit)


@public
def cancel_job(job_id: str) -> dict:
    from .dev_jobs import cancel

    return cancel(job_id)


@public
def verify_audio(output_path: str) -> dict:
    from .bulk_render import verified_output
    from .utils import sha256_of_file

    manifest = safe_path(output_path + "/session-report.json", work_root())
    ok = verified_output(
        {
            "key": "verify",
            "output_directory": str(manifest.parent),
            "manifest_sha256": sha256_of_file(manifest),
        },
        "verify",
    )
    return {
        "status": "passed" if ok else "failed",
        "verification": "manifest sizes and SHA-256; codec decoding was performed at render publication",
        "artifact": output_path,
    }


@public
def package_release(
    function_id: str,
    artwork: str | None = None,
    locale: str = "en-US",
    voice: str | None = None,
    dry_run: bool = True,
    confirmed: bool = False,
    artwork_theme: str | None = None,
) -> dict:
    from .dev_jobs import start

    owner(function_id)
    if artwork:
        safe_path(artwork, work_root())
    elif not artwork_theme:
        from .release import artwork_selection

        if artwork_selection(function_id)[2] is None:
            raise OCFError("provide explicit artwork or an explicit/configured artwork theme")
    if not dry_run and not confirmed:
        raise OCFError("explicit confirmed=true is required for release packaging")
    return start(
        "release",
        {
            "function_id": function_id,
            "artwork": artwork,
            "artwork_theme": artwork_theme,
            "locale": locale,
            "voice": voice,
            "dry_run": dry_run,
        },
    )


@public
def cache_diagnostics() -> dict:
    from .paths import work_path
    from .speech_cache import MAX_CACHE_BYTES, STATS

    entries = list(work_path("cache", "tts").glob("*/speech.wav"))
    from .dsp_cache import MAX_BYTES

    dsp_files = [p for p in work_path("cache", "dsp").glob("*/*") if p.is_file()]
    return {
        "dsp": {
            "bytes": sum(p.lstat().st_size for p in dsp_files),
            "max_bytes": MAX_BYTES,
            "entries": sum(p.name == "manifest.json" for p in dsp_files),
        },
        "process_counters": dict(STATS),
        "entries": len(entries),
        "bytes": sum(
            p.lstat().st_size for p in work_path("cache", "tts").glob("*/*") if p.is_file()
        ),
        "max_bytes": MAX_CACHE_BYTES,
        "policy": "content-addressed; writes bypassed at limit; explicit cleanup only",
    }


@public
def cache_clean(
    older_than_hours: float = 168, dry_run: bool = True, confirmed: bool = False, kind: str = "tts"
) -> dict:
    import math

    from .dev_jobs import lock

    if not math.isfinite(older_than_hours) or older_than_hours < 0:
        raise OCFError("cache age must be finite and nonnegative")
    if not dry_run and not confirmed:
        raise OCFError("cache deletion requires confirmed=true; preview with dry_run first")
    if kind not in {"tts", "dsp"}:
        raise OCFError("cache kind must be tts or dsp")
    with lock("speech-cache" if kind == "tts" else "dsp-cache", wait=True):
        return _clean_speech_cache(older_than_hours, dry_run, kind)


def _clean_speech_cache(older_than_hours: float, dry_run: bool, kind: str = "tts") -> dict:
    import shutil
    import time

    from .paths import work_path

    root = work_path("cache", kind)
    selected = []
    for folder in sorted(root.glob("*")):
        path = folder / ".ocf-cache-owned"
        if not path.is_file():
            path = folder / "manifest.json"
        if (
            folder.is_symlink()
            or path.is_symlink()
            or not path.is_file()
            or not re.fullmatch(r"[a-f0-9]{64}", folder.name)
        ):
            continue
        if (
            not folder.resolve().is_relative_to(root.resolve())
            or folder.stat().st_mtime > time.time() - older_than_hours * 3600
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            owned = (
                text == folder.name
                if path.name == ".ocf-cache-owned"
                else json.loads(text).get("key") == folder.name
            )
        except (OSError, ValueError, AttributeError):
            owned = False
        if owned:
            selected.append(folder.name)
            if not dry_run:
                shutil.rmtree(folder)
    return {"dry_run": dry_run, "selected_count": len(selected), "entries": page(selected, 0, 20)}


@public
def list_artwork_themes() -> dict:
    from .artwork import BRAND, theme_tokens

    return {
        "themes": [p.stem for p in sorted((BRAND / "themes").glob("*.json"))],
        "surfaces": {
            name: theme_tokens(name)["theme"]["id"] for name in ("ui", "artwork", "documentation")
        },
    }


@public
def inspect_brand() -> dict:
    from .artwork import identity
    from .brand_import import identity as imported_identity

    data = identity()
    return {key: value for key, value in data.items() if key != "geometry"} | {
        "imported_candidate": imported_identity(),
        "source": "brand/identity.json",
        "guide": "docs/BRANDING.md",
    }


@public
def validate_theme(theme: str, surface: str = "artwork") -> dict:
    from .artwork import BRAND, contrast, load_theme

    known = {p.stem for p in (BRAND / "themes").glob("*.json")}
    reference = theme
    if theme not in known:
        path = safe_path(theme, work_root())
        if path.stat().st_size > 262144:
            raise OCFError("custom theme exceeds 256 KiB")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("extends") not in known:
            raise OCFError(
                "MCP custom themes must inherit a registered built-in theme; arbitrary file inheritance is CLI-only"
            )
        reference = str(path)
    value = load_theme(reference, surface=surface)
    return {
        "status": "passed",
        "id": value["id"],
        "surface": surface,
        "contrast": contrast(value["palette"]["background"], value["palette"]["foreground"]),
    }


@public
def generate_artwork_preview(
    function_id: str, locale: str = "en-US", theme: str | None = None, resolution: int = 1400
) -> dict:
    from .dev_jobs import start

    return start(
        "artwork",
        {
            "function_id": function_id,
            "locale": locale,
            "theme": theme,
            "resolution": resolution,
        },
    )


@public
def list_voice_profiles(offset: int = 0, limit: int = 10) -> dict:
    from .indexes import load_voice_profiles
    from .voice import backend_locale_support

    rows = [
        {
            "id": p["id"],
            "name": p["name"],
            "backend": p["backend"],
            "language": p.get("language"),
            "model_sha256": p.get("model", {}).get("sha256"),
            "version": p.get("version"),
            "distribution_permission": p.get("distribution_permission", "unknown"),
            "consent_status": p.get("consent_status", "unknown"),
            "capabilities": backend_locale_support(p["backend"]),
        }
        for p in load_voice_profiles()
    ]
    return page(sorted(rows, key=lambda p: p["id"]), offset, limit)


@public
def validate_voice_dataset(manifest: str) -> dict:
    from .dev_jobs import start

    return start("voice-dataset", {"manifest": manifest})


@public
def inspect_voice_capabilities(probe_gpu: bool = False) -> dict:
    """Read local adapter metadata; GPU query is opt-in and bounded to two seconds."""
    from .voice_engine_cli import capabilities_report

    return capabilities_report(probe_gpu=probe_gpu)


@public
def plan_voice_training(backend: str = "piper", dataset: str | None = None) -> dict:
    from .voice_datasets import training_plan

    path = workspace_manifest(dataset, dataset=True)[0] if dataset is not None else None
    result = training_plan(path, backend=backend)
    if result.get("dataset"):
        result["dataset"] = {
            key: result["dataset"][key]
            for key in (
                "status",
                "dataset_id",
                "records",
                "errors",
                "warnings",
                "quality_summary",
                "readiness",
                "authorization_verified",
            )
        }
    return result


@public
def start_voice_audition(
    voices: list[str], locale: str = "en-US", idempotency_key: str | None = None
) -> dict:
    from .dev_jobs import start

    return start("voice-audition", {"voices": voices, "locale": locale}, idempotency_key)


@public
def inspect_release_artwork(manifest: str) -> dict:
    from .release import _validate_manifest

    path = safe_path(manifest, work_root())
    if path.suffix != ".json" or path.stat().st_size > 4 * 1024**2:
        raise OCFError("release manifest must be JSON, at most 4 MiB")
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_manifest(data)
    return {
        "function_id": data["function_id"],
        "provenance": data.get("artwork_provenance"),
        "artifacts": [r for r in data["artifacts"] if r["format"].startswith("image/")],
    }


TOOLS = {
    "ocf_" + f.__name__: f
    for f in (
        project_overview,
        list_functions,
        get_function,
        get_schema,
        get_workflow,
        get_audio_defaults,
        get_session_plan,
        validate_function,
        validate_locale,
        validate_commands,
        final_validation,
        select_tests,
        plan_audio,
        start_audio_render,
        run_tests,
        check_generated,
        get_job_status,
        get_job_result,
        cancel_job,
        verify_audio,
        package_release,
        cache_diagnostics,
        cache_clean,
        list_artwork_themes,
        inspect_brand,
        validate_theme,
        generate_artwork_preview,
        list_voice_profiles,
        validate_voice_dataset,
        plan_voice_training,
        start_voice_audition,
        inspect_release_artwork,
        inspect_narration_sources,
        validate_recordings,
        start_narration_render,
        inspect_voice_capabilities,
    )
}
READ_ONLY = {
    "ocf_" + f.__name__
    for f in (
        project_overview,
        list_functions,
        get_function,
        get_schema,
        get_workflow,
        get_audio_defaults,
        get_session_plan,
        validate_function,
        validate_locale,
        validate_commands,
        select_tests,
        plan_audio,
        get_job_status,
        get_job_result,
        verify_audio,
        cache_diagnostics,
        list_artwork_themes,
        inspect_brand,
        validate_theme,
        list_voice_profiles,
        plan_voice_training,
        inspect_release_artwork,
        inspect_narration_sources,
        inspect_voice_capabilities,
    )
}


def validate_tool_arguments(name: str, arguments: dict) -> None:
    """Validate the public argument contract without dispatching an operation."""
    if name not in TOOLS:
        raise OCFError("unknown developer operation")
    try:
        inspect.signature(TOOLS[name]).bind(**arguments)
    except TypeError as exc:
        raise OCFError(str(exc)) from exc
    hints = get_type_hints(TOOLS[name])

    def matches(value, hint):
        origin = get_origin(hint)
        if origin is types.UnionType:
            return any(matches(value, item) for item in get_args(hint))
        if origin is list:
            return isinstance(value, list) and all(matches(v, get_args(hint)[0]) for v in value)
        if hint is float:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return type(value) is hint

    for key, value in arguments.items():
        if not matches(value, hints[key]):
            raise OCFError(f"invalid argument type: {key}")


def dispatch(name: str, arguments: dict) -> dict:
    validate_tool_arguments(name, arguments)
    return TOOLS[name](**arguments)
