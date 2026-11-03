"""L2 activation at existing paths, retaining checked compatibility resources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from .locale import LocaleCatalog
from .localized_migration import _ReadableDumper, build_batch
from .paths import REPO_ROOT
from .utils import OCFError, yaml_safe_load

LEDGER = "function-content/editorial/localized-authority-003.json"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan(root=REPO_ROOT, *, records=None, catalog=None):
    catalog = catalog or LocaleCatalog(root / "locales")
    batch = build_batch(root, records=records, catalog=catalog)
    outputs = dict(batch["files"])
    manifest_name = "locales/en-US/manifest.yaml"
    manifest = yaml_safe_load((root / manifest_name).read_text(encoding="utf-8"))
    filenames = {Path(name).name for name in outputs}
    superseded = set()
    for text in outputs.values():
        data = yaml_safe_load(text)
        prefix = "functions." + data["function_id"].lower()
        superseded.update(
            prefix + "." + suffix for suffix in ("title", "purpose", "short-description")
        )
        superseded.update(data.get("metadata_entries", {}))
        superseded.update(
            row["description_key"] for row in data["relationships"]["related_functions"]
        )
        for row in [data["activation"], *data["secondary_commands"]]:
            command_prefix = "commands." + row["command_id"].lower()
            for field, suffix in [
                ("display_cue", "display-cue"),
                ("spoken_cue", "spoken-cue"),
                ("label", "label"),
                ("usage", "usage"),
                ("explanation", "explanation"),
            ]:
                if field in row:
                    superseded.add(command_prefix + "." + suffix)
    compatibility = {}
    for resource in manifest["resources"]:
        filename = resource["file"]
        if (
            filename == "OCF-EMO-003-Empathize.yaml"
            and catalog.require("en-US")
            .localized_functions.get("OCF-EMO-003", {})
            .get("title", {})
            .get("source")
            == "function-yaml"
        ):
            resource["file"] = "hplus-OCF-EMO-003.yaml"
            filename = resource["file"]
        if filename in filenames:
            resource["domain"] = "function"
            resource["description"] = (
                "Sole editable localized function metadata and canonical narration."
            )
        else:
            data = yaml_safe_load((root / "locales/en-US" / filename).read_text(encoding="utf-8"))
            keys = sorted(set(data.get("entries", {})) & superseded)
            if keys:
                resource["superseded_keys"] = keys
                resource["compatibility_sha256"] = digest(
                    json.dumps(data, sort_keys=True, ensure_ascii=False)
                )
                compatibility[filename] = keys
    outputs[manifest_name] = yaml.dump(
        manifest, Dumper=_ReadableDumper, sort_keys=False, allow_unicode=True, width=100
    )
    return {
        "outputs": outputs,
        "count": batch["count"],
        "compatibility": compatibility,
        "mapping": batch["mapping"],
        "removed_files": [],
        "renamed_files": [],
    }


def activate(preview, root=REPO_ROOT):
    ledger_path = root / LEDGER
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for name, row in ledger["files"].items():
            target = root / name
            if target.is_symlink() or not target.resolve().is_relative_to(
                (root / "locales/en-US").resolve()
            ):
                raise OCFError("unsafe localized activation target: " + name)
            if digest(target.read_text(encoding="utf-8")) != row["after_sha256"]:
                raise OCFError(
                    "activation already exists with changed source; preserve and reconcile: " + name
                )
        return {"count": ledger["count"], "ledger": LEDGER, "status": "already-active; no writes"}
    files = {}
    for name, after in preview["outputs"].items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(
            (root / "locales/en-US").resolve()
        ):
            raise OCFError("unsafe localized activation target: " + name)
        before = path.read_text(encoding="utf-8")
        files[name] = {
            "before": before,
            "before_sha256": digest(before),
            "after_sha256": digest(after),
        }
    ledger = {
        "schema_version": "1.0",
        "stage": "L2 literal authority activation; no retirement or renames",
        "count": preview["count"],
        "files": files,
        "compatibility": preview["compatibility"],
    }
    text = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    ledger_path.write_text(text, encoding="utf-8")
    for name, after in preview["outputs"].items():
        (root / name).write_text(after, encoding="utf-8", newline="\n")
    return {"count": preview["count"], "ledger": LEDGER, "ledger_sha256": digest(text)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    preview = plan()
    print(
        json.dumps(
            activate(preview)
            if args.apply
            else {key: value for key, value in preview.items() if key != "outputs"}
        )
    )


if __name__ == "__main__":
    main()
