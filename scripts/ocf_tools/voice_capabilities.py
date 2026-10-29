"""Local, read-only voice capability discovery; installation is not adapter readiness."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from copy import deepcopy

from .paths import work_path, workspace_run
from .utils import OCFError

_BACKENDS = {
    "piper": {
        "binary": "piper",
        "package": "piper",
        "upstream": {"basic_tts": True, "reference_inference": False, "training": True},
        "ocf": {
            "inference_supported": True,
            "training_supported": False,
            "cpu_tts": True,
            "customization_methods": ["installed-model", "trained-adapted"],
            "adapter_status": "working-basic-tts",
        },
        "guide": "https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/TRAINING.md",
        "license_note": "GPL engine; each model/dataset has separate terms.",
    },
    "espeak-ng": {
        "binary": "espeak-ng",
        "package": None,
        "upstream": {"basic_tts": True, "reference_inference": False, "training": False},
        "ocf": {
            "inference_supported": True,
            "training_supported": False,
            "cpu_tts": True,
            "customization_methods": ["installed-model"],
            "adapter_status": "working-basic-tts",
        },
        "guide": "https://github.com/espeak-ng/espeak-ng",
        "license_note": "Engine and voice data terms apply independently.",
    },
    "espeak": {
        "binary": "espeak",
        "package": None,
        "upstream": {"basic_tts": True, "reference_inference": False, "training": False},
        "ocf": {
            "inference_supported": True,
            "training_supported": False,
            "cpu_tts": True,
            "customization_methods": ["installed-model"],
            "adapter_status": "working-basic-tts",
        },
        "guide": "https://espeak.sourceforge.net/",
        "license_note": "Engine and voice data terms apply independently.",
    },
    "f5-tts": {
        "binary": None,
        "package": "f5_tts",
        "upstream": {"basic_tts": True, "reference_inference": True, "training": True},
        "ocf": {
            "inference_supported": False,
            "training_supported": False,
            "cpu_tts": False,
            "customization_methods": [],
            "adapter_status": "unverified-unsupported",
        },
        "guide": "https://github.com/SWivid/F5-TTS",
        "license_note": "MIT code; upstream pretrained models documented as CC-BY-NC. Do not infer redistribution permission.",
    },
    "chatterbox-nano": {
        "binary": None,
        "package": "chatterbox",
        "upstream": {"basic_tts": True, "reference_inference": True, "training": False},
        "ocf": {
            "inference_supported": True,
            "training_supported": False,
            "cpu_tts": True,
            "customization_methods": ["reference-audio"],
            "adapter_status": "implemented-inference-unverified",
        },
        "guide": "https://github.com/resemble-ai/chatterbox",
        "license_note": "Chatterbox Nano model card reports MIT; verify the exact selected model revision and dependency licenses.",
    },
}


def capability_registry() -> dict:
    """Return an independent snapshot of upstream features and shipped OCF adapters."""
    return deepcopy(_BACKENDS)


def _package_present(name: str) -> bool:
    # Inspect metadata only. In particular, do not import torch or initialize CUDA.
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def backend_capability(backend: str) -> dict:
    if backend not in _BACKENDS:
        raise OCFError(f"unknown voice backend: {backend}")
    spec = deepcopy(_BACKENDS[backend])
    if backend == "chatterbox-nano":
        root = work_path("cache").parent / "voice-envs/chatterbox"
        executable = (
            root / "Scripts/python.exe"
            if __import__("sys").platform == "win32"
            else root / "bin/python"
        )
        package = (
            any(root.glob("lib/python*/site-packages/chatterbox/__init__.py"))
            or (root / "Lib/site-packages/chatterbox/__init__.py").is_file()
        )
        metadata_files = list(
            root.glob("lib/python*/site-packages/chatterbox_tts-*.dist-info/METADATA")
        )
        try:
            version = next(
                (
                    line.partition(":")[2].strip()
                    for path in metadata_files
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("Version:")
                ),
                None,
            )
        except OSError:
            version = None
        spec["backend"] = backend
        spec["installation"] = {
            "executable_found": executable.is_file(),
            "package_found": package,
            "discovery": {
                "status": "ready" if executable.is_file() and package else "not-found",
                "source": "project-local optional environment" if executable.is_file() else None,
                "reason": None
                if executable.is_file() and package
                else "install docs/VOICE_PACKS.md optional dependencies",
                "runtime": {"package_version": version},
            },
        }
        spec["available"] = executable.is_file() and package
        return spec
    from .environment import resolve_executable

    discovery = resolve_executable(spec["binary"]) if spec["binary"] else None
    executable = (
        discovery.get("executable") if discovery and discovery["status"] == "ready" else None
    )
    spec["backend"] = backend
    runtime = discovery.get("runtime", {}) if discovery else {}
    safe_discovery = (
        {
            "status": discovery.get("status"),
            "source": discovery.get("source"),
            "reason": discovery.get("reason"),
            "runtime": {
                key: runtime.get(key)
                for key in (
                    "python_version",
                    "package_version",
                    "package_metadata_found",
                    "inference_verified",
                )
            },
        }
        if discovery
        else None
    )
    spec["installation"] = {
        "executable_found": executable is not None,
        "package_found": (
            bool(discovery and discovery.get("runtime", {}).get("status") == "ready")
            if backend == "piper"
            else _package_present(spec["package"])
            if spec["package"]
            else False
        ),
        "discovery": safe_discovery,
    }
    # Existing adapters execute binaries, not arbitrary importable Python packages.
    spec["available"] = spec["ocf"]["inference_supported"] and executable is not None
    return spec


def local_preflight(*, probe_gpu: bool = False, timeout: float = 2.0) -> dict:
    """Optional bounded local NVIDIA query; no downloads, torch imports or training."""
    result = {
        "torch_installed": _package_present("torch"),
        "gpu_probe": "not-requested",
        "gpus": [],
        "training_resources_verified": False,
        "resource_note": "Exact training memory/OS requirements depend on a pinned upstream configuration and remain unverified.",
    }
    if not probe_gpu:
        return result
    executable = shutil.which("nvidia-smi")
    if not executable:
        result["gpu_probe"] = "unavailable"
        return result
    try:
        completed = workspace_run(
            [executable, "--query-gpu=memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=min(max(float(timeout), 0.1), 5.0),
            check=False,
        )
        if completed.returncode:
            result["gpu_probe"] = "failed"
            return result
        for line in completed.stdout[:8192].splitlines()[:32]:
            total, free = (int(value.strip()) for value in line.split(","))
            if not 0 <= free <= total or total <= 0:
                raise ValueError("invalid GPU memory report")
            result["gpus"].append({"total_mib": total, "free_mib": free})
        result["gpu_probe"] = "reported" if result["gpus"] else "unavailable"
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        result["gpu_probe"] = "failed"
        result["gpus"] = []
    return result


def profile_capability(profile: dict) -> dict:
    """Report adapter/install readiness; callers separately validate assets/consent."""
    capability = backend_capability(profile["backend"])
    method = profile.get("customization_method", "installed-model")
    blockers = []
    if not capability["ocf"]["inference_supported"]:
        blockers.append("OCF inference adapter is unverified and unsupported for this backend.")
    if method not in capability["ocf"]["customization_methods"]:
        blockers.append(f"OCF adapter does not support customization method {method}.")
    if not capability["installation"]["executable_found"]:
        discovery = capability["installation"].get("discovery") or {}
        reason = discovery.get("reason") or discovery.get("status") or "not discovered"
        blockers.append(f"Required inference executable is unavailable ({reason}).")
    verified = False
    if profile.get("backend") == "chatterbox-nano" and capability["available"]:
        from .voice_packs import inference_verified

        verified = inference_verified(profile)
    return {
        "backend": profile["backend"],
        "customization_method": method,
        "available": not blockers,
        "inference_supported": capability["ocf"]["inference_supported"],
        "inference_verified": verified,
        "blockers": blockers,
        "capability": capability,
    }
