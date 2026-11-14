"""Path-free verification of canonical function semantics against hash baselines."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .function_catalog import resources, structural_contract
from .indexes import load_all_functions

BASELINE = (
    Path(__file__).resolve().parents[2] / "tests/fixtures/function-semantic-contract-baseline.json"
)


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify(root: Path | None = None, baseline_path: Path = BASELINE) -> list[str]:
    """Return semantic drift diagnostics; no source or predecessor YAML is read."""
    from .paths import REPO_ROOT

    root = root or REPO_ROOT
    expected = json.loads(baseline_path.read_text(encoding="utf-8"))["functions"]
    localized = {data["function_id"]: data for _, data in resources(root)}
    records = {record.id: record for record in load_all_functions(root=root)}
    problems = []
    if len(localized) != 58 or set(localized) != set(records) or set(localized) != set(expected):
        return ["canonical semantic baseline identity set differs from the 58-function catalog"]
    from .guide_review import approved_successor
    from .utils import OCFError

    successors = {}
    try:
        successors = approved_successor(root, snapshot=localized, records=records)["functions"]
    except OCFError as exc:
        problems.append(str(exc))
    for identity, baseline in expected.items():
        data, record = localized[identity], records[identity]
        narration = {
            key: (
                {field: value for field, value in entry.items() if field != "notes"}
                if isinstance(entry, dict)
                else entry
            )
            for key, entry in data["entries"].items()
        }
        presentation = {
            "function_id": identity,
            "title": data["title"]["text"],
            "description": data["description"]["text"],
            "activation": {
                "command_id": data["activation"]["command_id"],
                "display_cue": data["activation"].get("display_cue", {}).get("text"),
                "spoken_cue": data["activation"].get("spoken_cue", {}).get("text"),
            },
            "secondary_commands": [
                {
                    "command_id": row["command_id"],
                    "display_cue": row.get("display_cue", {}).get("text"),
                    "spoken_cue": row.get("spoken_cue", {}).get("text"),
                }
                for row in data["secondary_commands"]
            ],
        }
        checks = {
            "contract_sha256": digest(structural_contract(data)),
            "narration_sha256": digest(narration),
            "commands_sha256": digest(record.data["commands"]),
            "lifecycle_sha256": digest(record.data["lifecycle"]),
            "presentation_sha256": digest(presentation),
        }
        for field, actual in checks.items():
            approved = baseline[field]
            successor = successors.get(identity)
            if (
                field == "contract_sha256"
                and successor
                and approved == successor["previous_contract_sha256"]
            ):
                approved = successor["contract_sha256"]
            if actual != approved:
                problems.append(f"{identity}: canonical {field} differs from the approved baseline")
    return problems
