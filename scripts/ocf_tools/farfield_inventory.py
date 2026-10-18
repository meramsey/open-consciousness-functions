"""Pinned, offline-checkable Farfield preset provenance; never called by rendering."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from .paths import REPO_ROOT, workspace_run
from .utils import OCFError

REPOSITORY = "https://github.com/txus/farfield"
REVISION = "019fb804f3b274359e13e8cc9ca3b8fcaf9701f3"
REVIEW = "b6201835640cdbe13c96e43d68c839c8ac701942"
OCF_REVISION = "d92cb27cf5c89e6ed04a085099ec3538a9162748"
OCF_REPOSITORY = "https://github.com/meramsey/open-consciousness-functions"
INVENTORY = "audio/background/farfield-inventory.json"
MIRRORS = "audio/background/presets/farfield"
METADATA = frozenset({"name", "title", "notes", "fidelity"})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def acoustic_inputs(data: bytes) -> dict:
    """Compare every declared synthesis input, not a frequency allowlist."""
    document = yaml.safe_load(data)
    if not isinstance(document, dict):
        raise OCFError("Farfield preset must be a mapping")
    return {key: value for key, value in document.items() if key not in METADATA}


def local_presets(root: Path) -> list[Path]:
    return sorted(
        list((root / MIRRORS).glob("*.yaml"))
        + list((root / "audio/background/presets").glob("*.yaml"))
        + list((root / "presets/farfield").glob("*.yaml"))
    )


def check(root: Path = REPO_ROOT) -> list[str]:
    """Verify committed membership and bytes without network or an engine."""
    data = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
    errors = []
    if data["repository"] != REPOSITORY or data["revision"] != REVISION:
        errors.append("unexpected upstream identity")
    rows = data["presets"]
    names = [row["local_path"] for row in rows]
    actual = {path.relative_to(root).as_posix() for path in local_presets(root)}
    if len(names) != len(set(names)) or set(names) != actual:
        errors.append("preset inventory membership drift")
    for row in rows:
        name = row["local_path"]
        if name not in actual:
            continue
        if digest((root / name).read_bytes()) != row["sha256"]:
            errors.append("preset byte drift: " + name)
        if row["classification"] == "exact-upstream-mirror":
            if row["sha256"] != data["upstream_presets"].get(row["upstream_path"]):
                errors.append("upstream mirror hash mismatch: " + name)
    for name, expected in data["notices"].items():
        if digest((root / name).read_bytes()) != expected:
            errors.append("upstream notice drift: " + name)
    return errors


def refresh(checkout: Path, root: Path = REPO_ROOT) -> None:
    """Explicit maintainer operation from a locally fetched immutable revision.

    Frozen a/b/c aliases remain historical snapshots. Only same-named mirrors
    with identical complete synthesis mappings may be synchronized.
    """

    def git(*args: str) -> bytes:
        return workspace_run(
            ["git", "-C", str(checkout), *args], check=True, capture_output=True
        ).stdout

    upstream = {}
    updates = {}
    names = git("ls-tree", "--name-only", REVISION, "presets/").decode().splitlines()
    for name in names:
        if not name.endswith(".yaml"):
            continue
        content = git("show", f"{REVISION}:{name}")
        upstream[name] = digest(content)
        target = root / MIRRORS / Path(name).name
        if not target.is_file():
            raise OCFError("missing mirror requires explicit review: " + str(target))
        if acoustic_inputs(target.read_bytes()) != acoustic_inputs(content):
            raise OCFError("acoustic change requires review: " + name)
        updates[target] = content
    # Validate every candidate before publishing any metadata-only updates.
    rows = []
    for path in local_presets(root):
        local = path.relative_to(root).as_posix()
        source = "presets/" + path.name
        content = updates.get(path, path.read_bytes())
        staging = local.startswith("presets/")
        mirror = local.startswith(MIRRORS + "/") and source in upstream
        historical = local.startswith(MIRRORS + "/") and path.stem in {
            "focus-11-a",
            "focus-11-b",
            "focus-11-c",
        }
        classification = (
            "staging-only-contribution"
            if staging
            else "exact-upstream-mirror"
            if mirror
            else "historical-snapshot"
            if historical
            else "ocf-authored-extension"
        )
        rows.append(
            {
                "local_path": local,
                "sha256": digest(content),
                "classification": classification,
                "repository": REPOSITORY if mirror else OCF_REPOSITORY,
                "revision": REVISION if mirror else OCF_REVISION,
                "upstream_path": source if mirror else None,
                "intentional_modifications": (
                    "None; exact pinned bytes."
                    if mirror
                    else "Frozen pre-review contribution; original metadata retained, not upstream verification."
                    if historical or staging
                    else "OCF composition; not an upstream mirror."
                ),
                "current_fidelity": "best-effort"
                if historical or staging
                else yaml.safe_load(content).get("fidelity"),
            }
        )
    notices = {}
    for filename in ("NOTICE", "LICENSE"):
        path = root / "audio/background" / ("FARFIELD-" + filename)
        content = git("show", f"{REVISION}:{filename}")
        updates[path] = content
        notices[path.relative_to(root).as_posix()] = digest(content)
    data = {
        "schema_version": "1.0",
        "repository": REPOSITORY,
        "revision": REVISION,
        "reviewed_revision": REVIEW,
        "engine_revision_is_separate": True,
        "upstream_presets": upstream,
        "presets": rows,
        "notices": notices,
    }
    for path, content in updates.items():
        path.write_bytes(content)
    (root / INVENTORY).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-from", type=Path, help="explicit pinned local checkout")
    args = parser.parse_args(argv)
    if args.refresh_from:
        refresh(args.refresh_from)
    errors = check()
    print("\n".join(errors) if errors else "Pinned Farfield inventory: PASS")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
