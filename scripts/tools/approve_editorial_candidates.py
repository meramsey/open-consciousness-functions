"""One-shot implementation of the four explicitly approved candidate snapshots.

Pinned inputs and refusal to overwrite evidence make this an approval-specific
driver, not a general promotion or rebaseline command.
"""

import json
import subprocess

import yaml
from ocf_tools.candidate_approval import (
    APPROVED,
    BASELINE,
    LEDGER,
    MANIFEST,
    SNAPSHOTS,
    SOURCE,
    approved_function,
    sha,
)
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError, write_text_atomic


def main():
    from ocf_tools.audio_defaults import LOCK_PATH, create_lock
    from ocf_tools.cue_headers import header, split_header
    from ocf_tools.editorial_candidates import review
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.session_plans import generate_plans
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    root = REPO_ROOT
    if any((root / name).exists() for name in (LEDGER, BASELINE)) or LOCK_PATH.exists():
        raise OCFError("candidate successor already exists; never overwrite approval evidence")
    if any(r.id == "OCF-EXP-006" for r in load_all_functions()):
        raise OCFError("Intuition identity collision")

    def prior(name):
        return subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=root).decode(
            "utf-8"
        )

    def write(name, text):
        write_text_atomic(root / name, text)

    def dump(data):
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def yaml_text(data):
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)

    files = [
        MANIFEST,
        "functions/experimental/dissolve.yaml",
        "functions/experimental/clear-zone.yaml",
        "locales/en-US/original-OCF-EXP-003.yaml",
        "locales/en-US/original-OCF-EXP-005.yaml",
        "locales/en-US/original-draft-cues.yaml",
        "locales/en-US/original-draft-ui.yaml",
        "locales/en-US/manifest.yaml",
    ]
    files += [
        p.relative_to(root).as_posix()
        for p in sorted((root / "audio/session-plans/en-US").glob("*.json"))
    ]
    before = {name: prior(name) for name in files}
    if any((root / name).read_text(encoding="utf-8") != text for name, text in before.items()):
        raise OCFError("candidate migration inputs differ from approved source checkpoint")
    snapshots = {}
    for name in APPROVED:
        path = root / f"function-content/editorial/candidates/{name}.en-US.yaml"
        text = path.read_text(encoding="utf-8")
        if sha(text) != SNAPSHOTS[name]:
            raise OCFError("candidate wording differs from the presented snapshot")
        snapshots[name] = text
    staged_name = "function-content/editorial/candidates/intuition.function.yaml"
    staged = prior(staged_name)
    if staged != (root / staged_name).read_text(encoding="utf-8"):
        raise OCFError("Intuition procedure differs from reviewed proposal")
    new_files = [
        "functions/experimental/intuition.yaml",
        "locales/en-US/original-OCF-EXP-006.yaml",
        "function-content/bindings/OCF-EXP-006.yaml",
        "locales/en-US/intuition-ui.yaml",
        "locales/en-US/intuition-cues.yaml",
    ]
    if any((root / name).exists() for name in new_files):
        raise OCFError("new approval output already exists; preserve it")
    presented = {name: review(name) for name in APPROVED}
    old_texts = narration_texts(root)

    # Add status changes only. Original candidate files remain immutable.
    for name, (_, function, resource) in APPROVED.items():
        data = yaml.safe_load(snapshots[name])
        for entry in data["entries"].values():
            entry["status"] = "reviewed"
        # Preserve the supplied text layout, versions, notes and comments.
        promoted = snapshots[name].replace("    status: draft\n", "    status: reviewed\n")
        if yaml.safe_load(promoted) != data:
            raise OCFError("candidate promotion exceeds status-only change")
        write(resource, promoted)
        if name not in {"manifest-v2", "intuition"}:
            write(function, yaml_text(approved_function(yaml.safe_load(before[function]))))

    for name in ("locales/en-US/original-draft-cues.yaml", "locales/en-US/original-draft-ui.yaml"):
        data = yaml.safe_load(before[name])
        for entry in data["entries"].values():
            entry["status"] = "reviewed"
        write(name, yaml_text(data))

    intuition = approved_function(yaml.safe_load(staged))
    purpose_key = "functions.ocf-exp-006.purpose"
    intuition["documentation"] = {
        "title_key": "functions.ocf-exp-006.title",
        "purpose_key": purpose_key,
        "short_description_key": purpose_key,
    }
    command = intuition["commands"][0]
    prefix = "commands.ocf-cmd-exp-006-primary."
    command["localization"].update(
        {field + "_key": prefix + field for field in ("label", "usage", "explanation")}
    )
    write("functions/experimental/intuition.yaml", yaml_text(intuition))
    ui = {
        "functions.ocf-exp-006.title": "Intuition",
        purpose_key: intuition["purpose"]["summary"],
        prefix + "label": "Deliberate intuitive reinforcement",
        prefix
        + "usage": "Bring one question or situation into awareness; think or say Plus Intuition in the mind; allow a quiet moment; consider and choose a response.",
        prefix + "explanation": intuition["purpose"]["community_description"],
    }
    for filename, domain, entries in (
        ("intuition-ui.yaml", "ui", ui),
        ("intuition-cues.yaml", "narration", {prefix + "spoken-cue": command["spoken"]}),
    ):
        write(
            "locales/en-US/" + filename,
            yaml_text(
                {
                    "schema_version": "1.0",
                    "locale": "en-US",
                    "domain": domain,
                    "entries": {
                        key: {"text": text, "status": "reviewed"} for key, text in entries.items()
                    },
                }
            ),
        )
    binding = yaml.safe_load(
        (root / "function-content/bindings/OCF-EXP-003.yaml").read_text(encoding="utf-8")
    )
    binding.update(function_id="OCF-EXP-006", narration_plan=intuition["narration"])
    write("function-content/bindings/OCF-EXP-006.yaml", yaml_text(binding))
    additions = [
        {"file": "original-OCF-EXP-006.yaml", "domain": "narration"},
        {"file": "intuition-ui.yaml", "domain": "ui"},
        {"file": "intuition-cues.yaml", "domain": "narration"},
    ]
    manifest_name = "locales/en-US/manifest.yaml"
    write(
        manifest_name,
        before[manifest_name].replace("resources:\n", "resources:\n" + yaml_text(additions), 1),
    )

    catalog = LocaleCatalog()
    owners = {owner.id: owner for owner in load_all_functions()}
    for _, (identifier, _, resource) in APPROVED.items():
        body = split_header((root / resource).read_text(encoding="utf-8"))[1]
        write(resource, header(owners[identifier], "en-US", catalog, root) + body)
    previous_lock = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-009.json"
    create_lock(
        dependency_names=list(
            json.loads((root / previous_lock).read_text(encoding="utf-8"))["files"]
        )
    )
    generate_plans(locale="en-US")
    before.update({name: None for name in new_files})
    for identifier in ("OCF-EXP-003", "OCF-EXP-005", "OCF-EXP-006"):
        before[f"audio/session-plans/en-US/{identifier}.json"] = None
    texts = narration_texts(root)
    speech = {
        identity: {
            "before": text,
            "after": texts[identity],
            "before_sha256": sha(text),
            "after_sha256": sha(texts[identity]),
        }
        for identity, text in old_texts.items()
        if text != texts[identity]
    }
    if len(speech) != 3 or any(not identity.startswith(MANIFEST + "::") for identity in speech):
        raise OCFError("unexpected protected speech changes")
    immutable = {}
    for pattern in (
        "audio/defaults/*.json",
        "tests/fixtures/hplus-narration-text-baseline*.json",
        "function-content/editorial/*.json",
        "function-content/editorial/candidates/*.yaml",
        "functions/**/*.yaml",
    ):
        for path in root.glob(pattern):
            name = path.relative_to(root).as_posix()
            if name not in before and path != LOCK_PATH:
                immutable[name] = sha(path.read_text(encoding="utf-8"))
    data = {
        "schema_version": "1.0",
        "id": "OCF-APPROVED-CANDIDATES-001",
        "source_commit": SOURCE,
        "confirmation": "Confirm implementation",
        "approval_scope": "Exact presented narration, cues and procedures for all four candidates; Intuition registration; no DSP, pacing, listening or release approval.",
        "approvals": {
            name: {
                "function_id": APPROVED[name][0],
                "user_response": "1",
                "decision": "approve_full_draft",
                "snapshot_sha256": SNAPSHOTS[name],
                "resolved_sha256": {
                    entry["key"]: entry["resolved_text_sha256"] for entry in preview["entries"]
                },
            }
            for name, preview in presented.items()
        },
        "previous_baseline": "tests/fixtures/hplus-narration-text-baseline-006.json",
        "baseline": BASELINE,
        "previous_lock": previous_lock,
        "lock": LOCK_PATH.relative_to(root).as_posix(),
        "intuition_documentation": intuition["documentation"],
        "intuition_localization": command["localization"],
        "speech": speech,
        "unchanged_protected": {
            identity: sha(text) for identity, text in texts.items() if identity not in speech
        },
        "files": {
            name: {
                "before": old,
                "before_sha256": sha(old) if old is not None else None,
                "after_sha256": sha((root / name).read_text(encoding="utf-8")),
            }
            for name, old in before.items()
            if old != (root / name).read_text(encoding="utf-8")
        },
        "immutable_files": immutable,
        "listening_approval": False,
        "release_ready": False,
        "recording_cache_impact": "Manifest revised text changes resolved fingerprints and synthesis keys; old recordings remain stored and must not be relabelled. Other protected speech, including Options, is unchanged.",
    }
    write(BASELINE, dump(text_fingerprints(texts)))
    write(LEDGER, dump(data))
    print("Approval ledger SHA-256: " + sha(dump(data)))


if __name__ == "__main__":
    main()
