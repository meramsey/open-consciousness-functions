"""CLI support for `ocf audio ...` subcommands.

Combines engine detection, background preset listing/description, rendering, and
graceful degradation when the optional Farfield engine is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import farfield as farfield_mod
from . import sbagenx as sbagenx_mod
from .indexes import load_background_manifests
from .paths import REPO_ROOT, ensure_dir
from .utils import yaml_safe_dump


def check_engine() -> int:
    """`ocf audio check-engine`."""
    farfield_status = farfield_mod.check_farfield()
    if farfield_status.available:
        print("OCF background synthesis engine: farfield — AVAILABLE")
        print(f"  executable: {farfield_status.executable}")
        if farfield_status.version:
            print(f"  version:    {farfield_status.version}")
        print("  OCF invokes only the public CLI: farfield list|describe|render")
    else:
        print("OCF background synthesis engine: farfield — NOT AVAILABLE")
        print(farfield_mod.installation_guidance())

    sbagenx_status = sbagenx_mod.check_sbagenx()
    if sbagenx_status.available:
        print("OCF background synthesis engine: sbagenx — AVAILABLE")
        print(f"  executable: {sbagenx_status.executable}")
        if sbagenx_status.version:
            print(f"  version:    {sbagenx_status.version}")
        print("  OCF invokes only the public CLI: sbagenx -D|-SE -Wo")
    else:
        print("OCF background synthesis engine: sbagenx — NOT AVAILABLE")
        print("  " + sbagenx_mod.installation_guidance().replace("\n", "\n  "))
    return 0


def list_background() -> int:
    """`ocf audio list-background` — OCF presets plus engine listings."""
    manifests = load_background_manifests()
    print("OCF background presets (manifests):")
    if not manifests:
        print("  (none recorded; create one with: ./scripts/ocf new background)")
    for manifest in sorted(manifests, key=lambda m: str(m.get("id", ""))):
        print(f"  {manifest.get('id')}  {manifest.get('name')}  engine={manifest.get('engine')}")
    print("\nFarfield engine preset list:")
    print(farfield_mod.list_background_presets())
    print("  (OCF commits its own farfield preset files in audio/background/presets/farfield/)")
    print("\nSBaGenX engine programs:")
    print(sbagenx_mod.list_programs())
    print("  (OCF commits its own SBaGenX sequence files in audio/background/presets/sbagenx/)")
    return 0


def describe_background(preset: str, engine: str = "farfield") -> int:
    """`ocf audio describe-background <preset> [--engine farfield|sbagenx]`."""
    manifest = _find_manifest(preset)
    if manifest is not None:
        print(yaml_safe_dump(manifest))
        print("\nEngine description:")
    engine_file = _preset_engine_file(preset)
    if engine == "sbagenx":
        print(sbagenx_mod.describe_preset(engine_file or preset))
    else:
        print(farfield_mod.describe_preset(engine_file or preset))
    return 0


def render_background(
    preset: str, output: str | None = None, engine: str = "farfield"
) -> int:
    """`ocf audio render-background <preset> [--output FILE] [--engine ...]`."""
    manifest = _find_manifest(preset)
    out_path = Path(output) if output else None
    if manifest is not None:
        render = manifest.get("render", {})
        if out_path is None and render.get("output"):
            out_path = REPO_ROOT / str(render["output"])
    if out_path is not None:
        ensure_dir(out_path.parent)
    engine_file = _preset_engine_file(preset)
    if engine == "sbagenx":
        print(sbagenx_mod.render_preset(engine_file or preset, output=out_path))
    else:
        seed: int | None = None
        if manifest is not None:
            render = manifest.get("render", {})
            if render.get("seed") is not None:
                seed = int(render["seed"])
            if render.get("deterministic") and seed is not None:
                print(f"Deterministic render requested (seed {seed}).")
        print(farfield_mod.render_preset(engine_file or preset, output=out_path, seed=seed))
    return 0


def _preset_engine_file(query: str) -> str | None:
    """Resolve a background preset id/name to its `preset.file` on disk."""
    manifest = _find_manifest(query)
    if manifest is None:
        return None
    file_rel = (manifest.get("preset") or {}).get("file")
    if not file_rel:
        return None
    candidate = REPO_ROOT / str(file_rel)
    if candidate.is_file():
        return str(candidate)
    return None


def _find_manifest(query: str) -> dict[str, Any] | None:
    """Find a background manifest by id or name prefix."""
    for manifest in load_background_manifests():
        if manifest.get("id") == query or str(manifest.get("id", "")) == query.split(".")[0]:
            return manifest
        if str(manifest.get("name", "")).strip().lower() == query.strip().lower():
            return manifest
    return None
