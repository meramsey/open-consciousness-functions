"""Source extent and failure-path contracts with synthetic text only."""
import hashlib
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
SPEC = importlib.util.spec_from_file_location(
    "hplus_review_import",
    Path(__file__).resolve().parents[1] / "scripts/tools/prepare_hplus_function_review.py",
)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


def record(raw):
    return {
        "function_id": "OCF-COG-001", "source_availability": "available",
        "source_status": "transcript_unverified",
        "source": {"file": "synthetic.txt", "sha256": hashlib.sha256(raw).hexdigest(),
                   "line_count": len(raw.decode().splitlines())},
    }


def selection():
    return {"slots": {"opener": [{"start_line": 1, "end_line": 1}],
                      "function-body": [{"start_line": 2, "end_line": 2}]},
            "missing": {"closer": "No closer in supplied source."}, "notes": []}


def test_exact_unicode_and_within_line_boundaries_preserve_the_selected_words():
    text, locators = review.select_text(
        ["Function opener. To prepare for the shared section.", "Shared opening. Begin naïve recollection.", "Second line."],
        [{"start_line": 1, "end_line": 1, "end_before": "To prepare"},
         {"start_line": 2, "end_line": 3, "start_at": "Begin"}],
    )
    assert text == "Function opener.\n\nBegin naïve recollection.\nSecond line."
    assert "ends before" in locators and "starts at" in locators


@pytest.mark.parametrize("extents", [
    [{"start_line": 0, "end_line": 1}], [{"start_line": 2, "end_line": 1}],
    [{"start_line": 1, "end_line": 3}],
    [{"start_line": 1, "end_line": 2}, {"start_line": 2, "end_line": 2}],
    [{"start_line": 1, "end_line": 1, "start_at": "not present"}],
    [{"start_line": 1, "end_line": 1, "end_before": "not present"}],
])
def test_invalid_or_stale_boundaries_fail_instead_of_guessing(extents):
    with pytest.raises(ValueError):
        review.select_text(["First.", "Second."], extents)


def test_missing_sections_are_omitted_and_changed_source_is_rejected():
    raw = "Opener.\nBody — original wording.\n".encode()
    data, missing, _ = review.resource_for(record(raw), selection(), raw)
    assert data["entries"]["hplus.function.ocf-cog-001.function-body"]["text"] == "Body — original wording."
    assert "hplus.function.ocf-cog-001.closer" not in data["entries"]
    assert missing == selection()["missing"]
    with pytest.raises(ValueError, match="source hash changed"):
        review.resource_for(record(raw), selection(), b"Different source.\n")
    incomplete = selection()
    incomplete["missing"] = {}
    with pytest.raises(ValueError, match="explicit missing reason"):
        review.resource_for(record(raw), incomplete, raw)


def test_source_unavailable_status_is_not_a_spoken_placeholder_or_reconstruction():
    unavailable = {"function_id": "OCF-AUT-001", "source_availability": "unavailable", "source": None}
    data, missing, _ = review.resource_for(unavailable, None, None)
    assert data["domain"] == "ui" and len(missing) == 3
    assert list(data["entries"]) == ["hplus.review.ocf-aut-001.availability"]
    with pytest.raises(ValueError, match="inferred source wording"):
        review.resource_for(unavailable, selection(), b"reconstruction")


def proposed_fixture():
    raw = (
        "SEE-BE (test) — RECONSTRUCTED SCRIPT\nPLUS-AUTOMATE\nCLEAN RECORDING SCRIPT\n"
        "Proposed opener.\nProposed body.\nProposed closer.\nEND OF RECONSTRUCTED SCRIPT\n"
    ).encode()
    proposal = {
        "input": {"file": "proposal.txt", "header": raw.decode().splitlines()[0], "sha256": hashlib.sha256(raw).hexdigest()},
        "selection": {"slots": {slot: [{"start_line": line, "end_line": line}]
                                 for line, slot in enumerate(("opener", "function-body", "closer"), 4)},
                      "missing": {}, "notes": []},
    }
    historical = {"function_id": "OCF-AUT-001", "source_availability": "unavailable", "source": None}
    legacy = {"name": "SEE-BE", "commands": ["PLUS-AUTOMATE"]}
    return historical, proposal, raw, legacy


def test_explicit_proposal_preserves_words_without_relabeling_historical_source():
    historical, proposal, raw, legacy = proposed_fixture()
    before = deepcopy(historical)
    data, missing, notes = review.resource_for_proposal(historical, proposal, raw, legacy)
    assert historical == before and missing == {}
    assert data["domain"] == "narration"
    assert data["entries"]["hplus.function.ocf-aut-001.function-body"]["text"] == "Proposed body."
    assert all(entry["status"] == "draft" for entry in data["entries"].values())
    assert "not a recovered historical transcript" in notes[0]


@pytest.mark.parametrize("failure", ["hash", "header", "name", "command", "boundary", "slot", "historical"])
def test_proposal_identity_and_boundary_failures_are_not_guessed(failure):
    historical, proposal, raw, legacy = proposed_fixture()
    if failure == "hash":
        proposal["input"]["sha256"] = "0" * 64
    elif failure == "header":
        proposal["input"]["header"] = "Different title"
    elif failure == "name":
        legacy["name"] = "ANOTHER FUNCTION"
    elif failure == "command":
        legacy["commands"] = ["PLUS-OTHER"]
    elif failure == "boundary":
        proposal["selection"]["slots"]["opener"][0]["start_line"] = 1
    elif failure == "slot":
        del proposal["selection"]["slots"]["closer"]
    else:
        historical["source_availability"] = "available"
    with pytest.raises(ValueError):
        review.resource_for_proposal(historical, proposal, raw, legacy)


def test_proposal_production_directions_are_not_spoken():
    historical, proposal, raw, legacy = proposed_fixture()
    raw = raw.replace(b"Proposed body.", b"[Pause approximately thirty seconds.]")
    proposal["input"]["sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="production directions"):
        review.resource_for_proposal(historical, proposal, raw, legacy)
