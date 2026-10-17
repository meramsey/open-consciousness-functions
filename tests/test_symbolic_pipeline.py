"""Shared preview/audio-facing resolution, exact recording/cache identities."""

import json
from dataclasses import replace

import pytest
from ocf_tools import agent_api, cli, speech_cache
from ocf_tools.cue_templates import CueTemplateError, preview
from ocf_tools.locale import resolve_document
from test_cue_templates import fixture
from test_narration_sources import fixture as recording_fixture


@pytest.mark.integration
def test_cli_mcp_preview_parity_and_raw_resolved_fingerprints(capsys):
    assert cli.main(["functions", "preview", "OCF-SLP-005", "--locale", "en-US"]) == 0
    output = json.loads(capsys.readouterr().out)
    response = agent_api.get_function("OCF-SLP-005", locale="en-US", preview=True)
    assert response["data"]["narration_preview"] == output
    body = next(row for row in output["resources"] if row["role"] == "function-body")
    assert body["repetitions"] == 4
    assert "{{ cue.primary }}" in body["source_template"]
    assert "Plus Sleep Easy" in body["resolved_text"]
    assert body["raw_sha256"] != body["resolved_sha256"]
    assert output["synthesis"] is False


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_structural_conversion_reuses_recording_and_changed_spoken_cue_rejects_it(tmp_path, mode):
    from ocf_tools.narration_sources import SourceResolver, text_fingerprint

    owner, entry, catalog = fixture(tmp_path)
    doc, config, path = recording_fixture(tmp_path, mode=mode)
    doc["timeline"] = [{"id": "first", "at": 0, "narration_key": entry.key}]
    before_text = "Don't change  whitespace.\nThink Plus Example.\n"
    config["recordings"]["take"]["text_sha256"] = text_fingerprint(before_text)
    path.write_text(json.dumps(config), encoding="utf-8")
    original = path.read_bytes(), (tmp_path / "take.wav").read_bytes()
    resolved = resolve_document(doc, "en-US", catalog=catalog)
    assert resolved["timeline"][0]["text"].encode() == before_text.encode()
    assert SourceResolver(resolved, path).rows["first"]["recording_id"] == "take"
    owner.data["commands"][0]["spoken"] = "Plus Changed"
    catalog.canonical.entries["cue.example"] = replace(
        catalog.canonical.entries["cue.example"], text="Plus Changed"
    )
    changed = resolve_document(doc, "en-US", catalog=catalog)
    with pytest.raises(Exception, match="fingerprint"):
        SourceResolver(changed, path)
    assert original == (path.read_bytes(), (tmp_path / "take.wav").read_bytes())


@pytest.mark.unit
def test_semantic_template_errors_fail_even_in_explicit_fallback_auditions(tmp_path):
    owner, entry, catalog = fixture(tmp_path)
    catalog.canonical.entries[entry.key] = replace(entry, text="{{ env.SECRET }}")
    with pytest.raises(CueTemplateError, match="unknown or malformed"):
        resolve_document(
            {"locale": "en-US", "timeline": [{"id": "bad", "narration_key": entry.key}]},
            "en-US",
            strict=False,
            catalog=catalog,
        )


@pytest.mark.unit
def test_structural_templates_reuse_speech_cache_but_changed_cue_does_not(monkeypatch, tmp_path):
    from test_bulk_render import pcm

    owner, entry, catalog = fixture(tmp_path)
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"model": "same-model"})
    rendered = []

    def synthesize():
        rendered.append(1)
        return pcm()

    literal = "Don't change  whitespace.\nThink Plus Example.\n"
    symbolic = catalog.resource(entry.key, "en-US", domain="narration", fallback=False)[0].text
    with speech_cache.enabled():
        speech_cache.cached_cue({}, literal, synthesize)
        speech_cache.cached_cue({}, symbolic, synthesize)
        assert len(rendered) == 1
        owner.data["commands"][0]["spoken"] = "Plus Changed"
        catalog.canonical.entries["cue.example"] = replace(
            catalog.canonical.entries["cue.example"], text="Plus Changed"
        )
        changed = catalog.resource(entry.key, "en-US", domain="narration", fallback=False)[0].text
        speech_cache.cached_cue({}, changed, synthesize)
        assert len(rendered) == 2


@pytest.mark.unit
def test_wizard_owns_spoken_wording_once_and_leaves_new_review_unresolved():
    from ocf_tools.prompts import build_function_yaml

    row = build_function_yaml(
        function_id="OCF-COG-999",
        slug="example",
        name="Example",
        primary_domain="cognition",
        canonical_command="PLUS-EXAMPLE",
        spoken_cue="Plus Example",
        modes=["PLUS-MODE"],
        release_command="PLUS-END",
        command_status="unchanged",
    )
    assert row["commands"][0]["spoken"] == "Plus Example"
    assert row["commands"][0]["spoken_review"] == "unresolved"
    assert row["ocf"]["command_review"] == "needs-review"
    assert {command["role"] for command in row["commands"]} == {"activation", "mode", "release"}
    assert row["narration"] is None


@pytest.mark.unit
def test_preview_does_not_guess_unknown_function_or_missing_bindings(tmp_path):
    owner, entry, catalog = fixture(tmp_path)
    with pytest.raises(CueTemplateError, match="unknown function"):
        preview("unknown", records=[owner], catalog=catalog)
    owner.data["narration"] = None
    assert preview(owner.id, records=[owner], catalog=catalog)["resources"] == []


@pytest.mark.integration
def test_current_queue_excludes_finalized_cues_and_keeps_tentative_heart(tmp_path, monkeypatch):
    from ocf_tools import editorial_queue as review

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    queue = review.load_or_create()
    assert review.next_item(queue)["function_id"] == "OCF-BOD-014"
    ids = {row["function_id"] for row in queue["items"]}
    assert {"OCF-BOD-006", "OCF-BOD-010", "OCF-LIF-001"} <= ids
    assert not {"OCF-EXP-001", "OCF-SLP-005", "OCF-BOD-004", "OCF-BOD-003"} & ids
    assert all(row["status"] == "pending" for row in queue["items"])
    assert review.load_or_create() == queue
