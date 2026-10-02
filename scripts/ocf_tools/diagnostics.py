"""Core/workflow diagnostics; optional tools never fail core health."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sys

from .paths import FUNCTIONS_DIR, SCHEMAS_DIR

WORKFLOWS = {
    "core": (),
    "encode": ("ffmpeg", "ffprobe"),
    "farfield": ("farfield", "ffmpeg", "ffprobe"),
    "sbagenx": ("sbagenx",),
    "piper": ("piper",),
    "container": ("docker",),
}


def diagnose(
    workflow="core",
    *,
    which=None,
    version=None,
    module_available=None,
    schemas=None,
    functions=None,
) -> dict:
    if workflow not in WORKFLOWS:
        raise ValueError(f"unknown diagnostic workflow: {workflow}")
    which = which or shutil.which
    version = version or sys.version_info[:2]
    module_available = module_available or (lambda name: importlib.util.find_spec(name) is not None)
    checks = []

    def check(name, available, requirement, detail):
        checks.append(
            {
                "id": name,
                "status": "available" if available else "missing",
                "requirement": requirement,
                "detail": detail,
            }
        )

    check("python", version >= (3, 11), "core", f"{version[0]}.{version[1]}; need >=3.11")
    for name in ("yaml", "jsonschema", "referencing"):
        check(
            name,
            module_available(name),
            "core",
            "Python dependency; install project requirements if missing",
        )
    check(
        "schemas",
        SCHEMAS_DIR.is_dir() if schemas is None else schemas,
        "core",
        "authoritative packaged/source schemas",
    )
    check(
        "functions",
        FUNCTIONS_DIR.is_dir() if functions is None else functions,
        "core",
        "authoritative packaged/source function records",
    )
    for name in ("ffmpeg", "ffprobe", "farfield", "sbagenx", "piper", "docker", "podman"):
        path = which(name)
        check(
            name,
            bool(path),
            "workflow" if name in WORKFLOWS[workflow] else "optional",
            path or "not on PATH; install only for a workflow that needs it",
        )
    failures = [
        row["id"]
        for row in checks
        if row["status"] != "available" and row["requirement"] != "optional"
    ]
    return {
        "schema_version": "1.0",
        "workflow": workflow,
        "platform": platform.system(),
        "ok": not failures,
        "failures": failures,
        "checks": checks,
        "notes": [
            "Executable presence is not model/codec compatibility or OS certification",
            "No tools, models or containers executed or downloaded",
        ],
    }
