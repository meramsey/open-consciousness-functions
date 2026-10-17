"""Versioned shared defaults with a checked, content-addressed dependency lock."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from .paths import REPO_ROOT
from .utils import OCFError, sha256_of_file, write_text_atomic

PREVIOUS_BASELINE_ID = "OCF-AUDIO-DEFAULTS-HPLUS-001"
BASELINE_ID = "OCF-AUDIO-DEFAULTS-HPLUS-004"
BASELINE_VERSIONS = {
    PREVIOUS_BASELINE_ID: "1.0.0",
    "OCF-AUDIO-DEFAULTS-HPLUS-002": "2.0.0",
    "OCF-AUDIO-DEFAULTS-HPLUS-003": "3.0.0",
    BASELINE_ID: "4.0.0",
}
TEMPLATE_ID = "OCF-TPL-SESSION-HPLUS-LOCKED-001"
PACING_ID = "OCF-PACING-HPLUS-LOCKED-001"
DSP_ID = "OCF-DSP-HPLUS-LOCKED-001"
LOCK_PATH = REPO_ROOT / "audio" / "defaults" / f"{BASELINE_ID}.json"


def overlay(parent: dict, child: dict) -> dict:
    """Merge mappings recursively; arrays/scalars are explicit replacements."""
    result = deepcopy(parent)
    for key, value in child.items():
        result[key] = (
            overlay(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else deepcopy(value)
        )
    return result


def configuration_lock(
    dependency_names: list[str] | None = None, *, baseline_id: str = BASELINE_ID
) -> dict:
    from .semantic_dsp import load_profile
    from .session import load_pacing_profile, load_template

    if baseline_id not in BASELINE_VERSIONS:
        raise OCFError(f"unknown audio defaults baseline: {baseline_id}")
    template = load_template(TEMPLATE_ID)
    pacing = load_pacing_profile(PACING_ID)
    dsp = load_profile(DSP_ID)
    # Lock transitive stage, cue, preset and locale timing inputs too. Only
    # committed runtime inputs are inspected, never reference/source corpora.
    paths = set()
    for pattern in (
        "audio/templates/sessions/OCF-TPL-SESSION-HPLUS-*.yaml",
        "audio/templates/pacing/*.yaml",
        "audio/templates/stages/*.yaml",
        "audio/cues/*.yaml",
        "audio/background/manifests/OCF-BG-0012.yaml",
        "audio/background/manifests/OCF-BG-0006.yaml",
        "audio/background/presets/focus-10-v4-candidate.yaml",
        "audio/background/presets/farfield/focus-11-b.yaml",
        "audio/background/state-profiles/OCF-DSP-HPLUS-*.yaml",
        "locales/en-US/hplus-*.yaml",
    ):
        paths.update(REPO_ROOT.glob(pattern))
    if dependency_names is not None:
        paths = set()
        for name in dependency_names:
            path = (REPO_ROOT / name).resolve()
            if Path(name).is_absolute() or not path.is_relative_to(REPO_ROOT):
                raise OCFError("audio defaults dependency escapes repository")
            paths.add(path)
    return {
        "schema_version": "1.0",
        "id": baseline_id,
        "version": BASELINE_VERSIONS[baseline_id],
        "configuration_status": "locked-user-requested",
        "human_listening_approval": None,
        "release_ready": False,
        "compatibility": {
            "python": ">=3.11",
            "timing": "measured-speech-relative",
            "locale": "en-US",
        },
        "profiles": {
            name: {"id": data["id"], "version": data["version"]}
            for name, data in (("template", template), ("pacing", pacing), ("dsp", dsp))
        },
        "files": {
            path.relative_to(REPO_ROOT).as_posix(): sha256_of_file(path) for path in sorted(paths)
        },
    }


def check_lock(path: Path = LOCK_PATH) -> dict:
    recorded = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    baseline_id = recorded.get("id", BASELINE_ID)
    if path.name != f"{baseline_id}.json":
        raise OCFError("audio defaults lock identity/path mismatch")
    if baseline_id == BASELINE_ID:
        predecessor = json.loads(
            (REPO_ROOT / "audio/defaults" / f"{PREVIOUS_BASELINE_ID}.json").read_text(
                encoding="utf-8"
            )
        )
        if set(recorded.get("files", {})) != set(predecessor["files"]):
            raise OCFError(
                "successor audio defaults dependency membership differs from predecessor"
            )
    # New unrelated functions/locales do not mutate an existing baseline.
    # A change to a locked input still fails exact content verification.
    expected = configuration_lock(list(recorded.get("files", {})), baseline_id=baseline_id)
    if recorded != expected:
        raise OCFError(
            "shared audio defaults lock is stale; create a new baseline version deliberately"
        )
    return expected


def create_lock(
    path: Path = LOCK_PATH,
    *,
    baseline_id: str = BASELINE_ID,
    dependency_names: list[str] | None = None,
) -> None:
    if path.exists():
        raise OCFError(f"immutable audio defaults lock already exists: {path.name}")
    if path.name != f"{baseline_id}.json":
        raise OCFError("audio defaults lock identity/path mismatch")
    write_text_atomic(
        path,
        json.dumps(
            configuration_lock(dependency_names, baseline_id=baseline_id),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        overwrite=False,
    )
