"""One-shot confirmed guide metadata successor; no audio or narration writing."""

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.guide_review import (  # noqa: E402
    EDGES,
    LEDGER,
    STEP_TEXT,
    check_function_scope,
    revised_purpose,
    sha,
)
from ocf_tools.indexes import load_all_functions  # noqa: E402
from ocf_tools.paths import REPO_ROOT  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic  # noqa: E402
from tools.create_command_simplification import replace_entry  # noqa: E402

SOURCE = "2b26883148ee1c218a917cd7ff4119943d2eb03f"
EXPLANATIONS = [
    "Compare intention-setting with releasing a selected unwanted pattern. These remain independent exercises, not a required sequence.",
    "Intuition offers a separately chosen exercise for exploring understanding alongside purposeful intention-setting. Intuitive impressions are not proof or instructions that must be followed.",
    "Distinguish releasing a selected unwanted pattern from exploring intuitive understanding. Either exercise may be chosen independently; neither is a prerequisite for the other.",
    "Compare heart-oriented calm and steadiness with broader circulation-oriented comfort. These are independently selectable wellness exercises, not a combined treatment or a proven way to improve cardiovascular function.",
    "Compare sleep support for unfamiliar or distracting surroundings with an exercise oriented toward restorative rest. Choose independently; this link does not prescribe combining or stacking recordings.",
    "Compare directed-attention practice with thinking-oriented practice. Choose either independently; neither is required to activate or benefit from the other. The Focus function is not a Focus 10/11 audio stage.",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path, help="local confirmed FUNCTION_GUIDE_REVIEW.json")
    args = parser.parse_args()
    root = REPO_ROOT
    if (root / LEDGER).exists():
        raise OCFError("immutable guide approval successor already exists")
    review = json.loads(args.review.read_text(encoding="utf-8"))
    if (
        review["source_commit"] != SOURCE
        or review["implementation_confirmation"]["exact_user_response"] != "Yes"
        or len(review["queue"]) != 6
        or any(
            x["decision_status"] != "approved" or x["exact_user_responses"] != ["1"]
            for x in review["queue"]
        )
    ):
        raise OCFError("guide review lacks the complete confirmed decision batch")
    files = {}
    pending = {}

    def prior(name):
        text = (root / name).read_text(encoding="utf-8")
        committed = subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=root).decode()
        if text != committed:
            raise OCFError("guide successor input differs from verified source: " + name)
        return text

    for name in ("locales/en-US/commands.yaml", "locales/en-US/ui.yaml"):
        pending[name] = prior(name)

    def update_ui(name, key, text):
        def update(entry):
            version = str(entry.get("version", "0.0.0")).split(".")
            version[-1] = str(int(version[-1]) + 1)
            entry.update(
                text=text,
                status="reviewed",
                version=".".join(version),
                notes="Documentation-only approval OCF-GUIDE-REVIEW-001; not narration, listening or release approval.",
            )

        pending[name] = replace_entry(pending[name], key, update)

    for record in load_all_functions():
        name = record.path.relative_to(root).as_posix()
        before = record.data
        after = deepcopy(before)
        if record.id in EDGES:
            after["companions"] = EDGES[record.id]
        for field in ("summary", "community_description"):
            after["purpose"][field] = revised_purpose(record.id, before["purpose"][field])
        if record.id == "OCF-EXP-006":
            for step in after["commands"][0]["procedure"]["override_steps"]:
                key = f"functions.ocf-exp-006.procedure.{step['id']}"
                step["localization_key"] = key
                update_ui("locales/en-US/ui.yaml", key, STEP_TEXT[step["id"]])
        if after != before:
            check_function_scope(before, after)
            prior(name)
            pending[name] = yaml.safe_dump(after, allow_unicode=True, sort_keys=False, width=100)
        if after["purpose"]["summary"] != before["purpose"]["summary"]:
            for key in set(
                record.documentation[k] for k in ("purpose_key", "short_description_key")
            ):
                update_ui("locales/en-US/commands.yaml", key, after["purpose"]["summary"])

    decisions = []
    for question, text in zip(review["queue"], EXPLANATIONS, strict=True):
        row = question["current_source_evidence"]
        key = "relationships." + row["relationship_id"].lower() + ".description"
        update_ui("locales/en-US/ui.yaml", key, text)
        decisions.append(
            {
                "relationship_id": row["relationship_id"],
                "source_id": row["source_id"],
                "related_id": row["related_id"],
                "dependency": "optional",
                "response": "1",
                "description_key": key,
                "approved_explanation": text,
                "provenance": "Existing proposal docs/FUNCTION_GUIDES.md; one-question-at-a-time explicit approval; final confirmation Yes.",
                "reciprocal_approved": False,
            }
        )
    for name, text in pending.items():
        before = prior(name)
        if text != before:
            files[name] = {
                "before": before,
                "before_sha256": sha(before),
                "after_sha256": sha(text),
            }
    data = {
        "schema_version": "1.0",
        "id": "OCF-GUIDE-REVIEW-001",
        "source_commit": SOURCE,
        "confirmation": "Yes",
        "decisions": decisions,
        "files": files,
        "scope": "Description/optional companion/step-label metadata only. No cue, procedure operation/order, lifecycle, narration, audio, DSP or release change.",
        "imprint_authority": "OCF-FUNCTIONAL-METADATA-001:OCF-COG-004:persistence; retained material and separate deliberate recall already approved.",
    }
    for name in files:
        write_text_atomic(root / name, pending[name])
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text_atomic(root / LEDGER, text, overwrite=False)
    print("Pin LEDGER_SHA256 to " + sha(text))


if __name__ == "__main__":
    main()
