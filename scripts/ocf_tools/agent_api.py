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
    if "\\" in value or PureWindowsPath(value).drive:
        raise OCFError("use a relative forward-slash path")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise OCFError("path must be relative and contained")
    path = (root / candidate).resolve()
    if not path.is_relative_to(root.resolve()) or (exists and not path.is_file()):
        raise OCFError("path is unavailable or outside the allowed root")
    return path


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
    from .audio_defaults import check_lock
    from .session_plans import digest

    lock = check_lock()
    return {key: value for key, value in lock.items() if key != "files"} | {
        "sha256": digest(lock),
        "locked_files": len(lock["files"]),
        "artifact": "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json",
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
        "sha256": compact["generation"]["semantic_plan_sha256"],
        "artifact": f"audio/session-plans/{compact['locale']}/{function_id}.json",
    }
    if stages:
        result["stages"] = expanded["stages"]
        result["dsp_transitions"] = expanded["effective_state_directives"]
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
    artwork: str,
    locale: str = "en-US",
    voice: str | None = None,
    dry_run: bool = True,
    confirmed: bool = False,
) -> dict:
    from .dev_jobs import start

    owner(function_id)
    safe_path(artwork, work_root())
    if not dry_run and not confirmed:
        raise OCFError("explicit confirmed=true is required for release packaging")
    return start(
        "release",
        {
            "function_id": function_id,
            "artwork": artwork,
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
    return {
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
    older_than_hours: float = 168, dry_run: bool = True, confirmed: bool = False
) -> dict:
    import math

    from .dev_jobs import lock

    if not math.isfinite(older_than_hours) or older_than_hours < 0:
        raise OCFError("cache age must be finite and nonnegative")
    if not dry_run and not confirmed:
        raise OCFError("cache deletion requires confirmed=true; preview with dry_run first")
    with lock("speech-cache", wait=True):
        return _clean_speech_cache(older_than_hours, dry_run)


def _clean_speech_cache(older_than_hours: float, dry_run: bool) -> dict:
    import shutil
    import time

    from .paths import work_path

    root = work_path("cache", "tts")
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
    )
}


def dispatch(name: str, arguments: dict) -> dict:
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
    return TOOLS[name](**arguments)
