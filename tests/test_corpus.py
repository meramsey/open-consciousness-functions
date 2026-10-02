"""Research provenance stays separate from apparent completeness and OCF quality."""

import json
from pathlib import Path

import pytest
from ocf_tools.corpus import candidate_locators, classify, inventory, markdown, normalized
from ocf_tools.utils import OCFError
from ocf_tools.validators import _load_schema, validate_against_schema


def test_mockup_statement_outranks_source_folder():
    assert (
        classify(
            Path("+Transcripts From available tapes/Test/complete.txt"),
            "A reconstructed transcript, not a recovered transcript.",
        )[0]
        == "reconstructed_mockup"
    )
    assert classify(Path("complete.txt"), "A very fluent complete instruction.")[0] == "unknown"
    assert classify(Path("notes.md"), "Research about a function")[0] == "secondary_description"
    assert classify(Path("function.pdf"), None)[0] == "unknown"
    assert (
        classify(
            Path("annotated.txt"), "This is a reconstruction, not a recovered original transcript."
        )[0]
        == "reconstructed_mockup"
    )


def test_partial_source_and_locator_candidates_not_verbatim_exports():
    text = "To prepare for a function exercise\nHere is the instruction\n...\nThe end of your function learning exercise"
    path = Path("+Transcripts From available tapes/Relax/Relax.txt")
    assert classify(path, text)[0] == "partial_source_transcript"
    locators = candidate_locators(text)
    assert locators["main"] == [2] and locators["closer"] == [4]
    assert candidate_locators(None) == {}
    assert normalized("Möbius West") == "mobiuswest"


def test_inventory_maps_all_targets_without_changing_inputs(tmp_path):
    source = tmp_path / "+Transcripts From available tapes" / "Relax"
    source.mkdir(parents=True)
    path = source / "Relax.txt"
    original = b"To prepare for your function exercise\nPRIVATE SOURCE WORDING"
    path.write_bytes(original)
    mockup = tmp_path / "Sleep Easy"
    mockup.mkdir()
    (mockup / "script.txt").write_text("Research reconstruction, not a recovered transcript")
    data = inventory(tmp_path)
    assert not validate_against_schema(data, _load_schema("corpus-inventory.schema.json"))
    assert data["counts"]["target_functions"] == 55
    assert data["counts"]["distinct_functions"] == 2
    assert data["counts"]["independently_verified_transcripts"] == 0
    assert path.read_bytes() == original
    assert "PRIVATE SOURCE WORDING" not in json.dumps(data)
    assert "OCF-SLP-005" in markdown(data)
    assert len(data["functions"]) == 55
    with pytest.raises(OCFError, match="not found"):
        inventory(tmp_path / "absent")


def test_cli_json_and_protect_reference_output(tmp_path, capsys):
    from ocf_tools.cli import main

    (tmp_path / "unknown.txt").write_text("No provenance statement")
    assert main(["corpus", "inventory", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["counts"]["file_count"] == 1
    assert (
        main(
            [
                "corpus",
                "inventory",
                "--root",
                str(tmp_path),
                "--output",
                str(tmp_path / "derived.json"),
            ]
        )
        == 1
    )
    assert not (tmp_path / "derived.json").exists()
