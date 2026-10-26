"""Repository integration: exact drafts, separate review, strict production gates."""

import hashlib
import json
from copy import deepcopy

import pytest
from ocf_tools.commands import resolve_procedure, validate_command_collection
from ocf_tools.editorial_candidates import CANDIDATES, DIRECTORY, LEDGER, review
from ocf_tools.indexes import load_all_functions, load_yaml_file
from ocf_tools.locale import LocaleCatalog, iter_events
from ocf_tools.narration_first import plan_narration
from ocf_tools.paths import REPO_ROOT
from ocf_tools.prompts import next_function_id
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_preview_preserves_status_text_and_four_passes(name):
    before = (REPO_ROOT / "locales/en-US/hplus-OCF-EXP-001.yaml").read_bytes()
    result = review(name)
    assert result["editorial_status"] == "approved"
    assert result["snapshot_status"] == "draft"
    assert result["production_authorized"] is True
    assert result["release_ready"] is False
    assert [row["repetitions"] for row in result["entries"]] == [1, 4, 1]
    events = list(iter_events(result["semantic_plan"]))
    assert len([row for row in events if row.get("slot_ref") == "function_body"]) == 4
    assert all("{{" not in row["text"] for row in result["entries"])
    assert before == (REPO_ROOT / "locales/en-US/hplus-OCF-EXP-001.yaml").read_bytes()
    with pytest.raises(OCFError):
        review(name, locale="es")


def test_supplied_snapshots_and_generated_resources_remain_exact():
    ledger = json.loads((REPO_ROOT / LEDGER).read_text(encoding="utf-8"))
    for name, checksum in ledger["snapshots"].items():
        assert hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest() == checksum
    for slug, identifier in (("dissolve", "OCF-EXP-003"), ("clear-zone", "OCF-EXP-005")):
        original = load_yaml_file(DIRECTORY / f"{slug}.en-US.yaml")
        approved = deepcopy(original)
        for entry in approved["entries"].values():
            entry["status"] = "reviewed"
        assert load_yaml_file(REPO_ROOT / f"locales/en-US/original-{identifier}.yaml") == approved
    assert [row["version"] for row in review("manifest-v2")["entries"]] == [
        "1.2.0",
        "2.0.0",
        "1.3.0",
    ]


@pytest.mark.parametrize("identifier", ["OCF-EXP-003", "OCF-EXP-005"])
def test_explicitly_approved_originals_keep_provenance_and_locale_gates(identifier):
    owner = next(row for row in load_all_functions() if row.id == identifier)
    assert owner.audio_script_status == "approved"
    assert owner.data["legacy"]["source_system"] is None
    assert not owner.data["sources"]
    assert not validate_command_collection([owner])
    assert validate_command_collection([owner, owner])
    assert plan_narration(identifier)
    with pytest.raises(OCFError):
        LocaleCatalog().resource(
            f"hplus.function.{identifier.lower()}.function-body",
            "es",
            domain="narration",
            fallback=False,
        )


def test_distinct_clear_zone_ids_and_exact_procedure():
    owner = next(row for row in load_all_functions() if row.id == "OCF-EXP-005")
    assert [(row.id, row.data["spoken"]) for row in owner.command_records] == [
        ("OCF-CMD-EXP-005-PRIMARY", "Plus Clear Zone"),
        ("OCF-CMD-EXP-005-OBSERVE", "Plus Clear Zone, Observe"),
        ("OCF-CMD-EXP-005-SUSPEND", "Plus Clear Zone, Suspend"),
    ]
    for command in owner.command_records:
        assert [step["operation"] for step in resolve_procedure(command, {})] == [
            "inhale",
            "think-or-say-command",
            "exhale",
        ]
    descriptions = " ".join(owner.data["lifecycle"]["trigger_conditions"])
    for phrase in (
        "mutually exclusive",
        "normal sleep onset",
        "loss of consciousness",
        "deliberate primary invocation",
        "not reset",
        "not executable",
    ):
        assert phrase in descriptions
    body = review("clear-zone")["entries"][1]
    assert {row["provenance"].get("command_id") for row in body["references"]} >= {
        "OCF-CMD-EXP-005-PRIMARY",
        "OCF-CMD-EXP-005-OBSERVE",
        "OCF-CMD-EXP-005-SUSPEND",
    }


def test_dissolve_procedure_and_intuition_staging():
    owner = next(row for row in load_all_functions() if row.id == "OCF-EXP-003")
    assert [step["operation"] for step in resolve_procedure(owner.command_records[0], {})] == [
        "select-intention",
        "inhale",
        "hold-breath",
        "think-or-say-command",
        "exhale",
    ]
    assert next_function_id("experimental") == "OCF-EXP-007"
    assert "OCF-EXP-006" in {row.id for row in load_all_functions()}
    candidate = load_yaml_file(DIRECTORY / "intuition.function.yaml")
    assert candidate["commands"][0]["procedure"]["status"] == "unresolved"
    assert review("intuition")["entries"][0]["text"] == (
        "This OCF exercise will strengthen your intuitive awareness, bringing the wisdom of your heart, subconscious mind, and higher self into clear understanding and purposeful action."
    )
