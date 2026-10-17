"""Regenerate's approved teaching and the two-successor historical chain."""

import json

import pytest
import yaml
from ocf_tools import editorial_successors as successors
from ocf_tools.commands import cue_presentation, is_active
from ocf_tools.indexes import load_function_by_id
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError

OWNER = "OCF-BOD-014"
OLD = "Plus Build Live"
NEW = "Plus Regenerate"


@pytest.mark.integration
def test_regenerate_exact_scope_and_all_predecessors_remain_valid():
    from ocf_tools.cue_migration import verify_migration
    from ocf_tools.narration_first import plan_narration
    from ocf_tools.symbolic_integrity import verify as verify_structure
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    assert successors.verify() == verify_migration() == verify_structure() == []
    ledger = successors.records()[1]
    decision = ledger["decisions"][0]
    current = text_fingerprints(narration_texts())
    for later in reversed(successors.records()[2:]):
        for change in later["allowed_text_changes"]:
            assert current[change["identity"]] == change["after_sha256"]
            current[change["identity"]] = change["before_sha256"]
    previous = json.loads((REPO_ROOT / ledger["previous_integrity_baseline"]).read_text())
    assert len(current) == len(previous) == 177
    assert {key for key in current if current[key] != previous[key]} == {
        row["identity"] for row in ledger["allowed_text_changes"]
    }
    assert [row["substitutions"] for row in ledger["allowed_text_changes"]] == [
        [{"before": OLD, "after": NEW, "count": 2}],
        [{"before": OLD, "after": NEW, "count": 1}],
    ]
    owner = load_function_by_id(OWNER)
    prior = yaml.safe_load(ledger["predecessor_files"][decision["function_file"]])
    assert owner.data["legacy"] == prior["legacy"]
    assert owner.data["legacy"]["source_availability"] == "unavailable"
    assert owner.data["lifecycle"] == prior["lifecycle"]
    assert owner.persistence == "permanent" and owner.command_modes == []
    assert owner.canonical_name == "Regenerate"
    assert all(item["kind"] != "former-title" for item in owner.data["historical_lookup"])
    assert cue_presentation(owner, strict=True)["spoken_cue"] == NEW
    assert {row.id for row in owner.command_records if is_active(row)} == {
        "OCF-CMD-BOD-014-PRIMARY"
    }
    plan = plan_narration(OWNER, locale="en-US")
    for playback in range(1, 5):
        text = "\n\n".join(
            row["canonical_text"]
            for row in plan["segments"]
            if row["role"] == "function-body" and row["playback"] == playback
        )
        assert text.count(NEW) == 2 and OLD not in text and "{{" not in text
    closer = "\n\n".join(
        row["canonical_text"] for row in plan["segments"] if row["role"] == "closer"
    )
    assert closer.count(NEW) == 1 and "OCF Regenerate exercise" in closer and OLD not in closer
    # Both editorial successors unwind to the structural revision, including shared files.
    first = successors.records()[0]
    for name in (
        "locales/en-US/commands.yaml",
        "locales/en-US/activation-cues.yaml",
        "locales/en-US/manifest.yaml",
    ):
        assert successors.before_file(REPO_ROOT, name) == first["predecessor_files"][name]
    original = json.loads((REPO_ROOT / first["previous_integrity_baseline"]).read_text())
    assert text_fingerprints(successors.before_texts(REPO_ROOT, narration_texts())) == original


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_build_live_recordings_are_stale_including_explicit_tts_fallback(tmp_path, mode):
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.narration_sources import SourceResolver
    from test_narration_sources import fixture

    doc, config, path = fixture(tmp_path, mode=mode)
    old = successors.records()[1]["allowed_text_changes"][0]
    entry, _ = LocaleCatalog().resource(
        "hplus.function.ocf-bod-014.function-body", "en-US", domain="narration", fallback=False
    )
    doc["timeline"] = [{"id": "first", "at": 0, "text": entry.text}]
    config["recordings"]["take"]["text_sha256"] = old["before_sha256"]
    config["fallback"] = "tts"
    path.write_text(json.dumps(config), encoding="utf-8")
    originals = path.read_bytes(), (tmp_path / "take.wav").read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(doc, path)
    assert originals == (path.read_bytes(), (tmp_path / "take.wav").read_bytes())


@pytest.mark.integration
def test_build_live_lookup_remains_historical_without_selecting_activation():
    from ocf_tools.vocabulary import lookup

    for phrase in ("PLUS-BUILD, LIVE", OLD):
        row = next(item for item in lookup(phrase) if item["function_id"] == OWNER)
        assert row["title"] == "Regenerate" and row["cue"]["spoken_cue"] == NEW
        assert row["activation_selected"] is False
        assert all(match["historical"] for match in row["matches"])


@pytest.mark.integration
@pytest.mark.parametrize("field", ["title", "display_cue", "spoken_cue"])
def test_regenerate_predecessor_is_pinned_before_projection(tmp_path, field):
    data = successors.records()[1]
    data["decisions"][0]["previous"][field] = "inhale"
    target = tmp_path / successors.REGISTERED[1]
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OCFError, match="predecessor wording"):
        successors.before_texts(tmp_path, {})
