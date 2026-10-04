"""Validator orchestration against injected schema, discovery and library boundaries."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from ocf_tools import (
    audio_build,
    content,
    indexes,
    semantic_dsp,
    semantics,
    session,
    transcript,
    voice_registry,
)
from ocf_tools import validators as v
from ocf_tools.models import function_from_dict
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def codes(result):
    return {issue.code for issue in result.issues}


def finding(code, severity="error"):
    result = v.ValidationResult()
    result.add(severity, code, "fixture diagnostic")
    return result


@pytest.fixture
def schema_boundary(monkeypatch):
    monkeypatch.setattr(v, "_load_schema", lambda name: {"title": name})
    monkeypatch.setattr(
        v,
        "validate_against_schema",
        lambda data, schema: ["invalid fixture"] if data.get("invalid") else [],
    )


def test_local_schema_registry_resolves_shared_refs_without_network(monkeypatch, tmp_path):
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://example.invalid/fixture",
        "type": "object",
        "properties": {"value": {"type": "integer"}},
    }
    path = tmp_path / "fixture.schema.json"
    path.write_text(json.dumps(schema))
    monkeypatch.setattr(v, "schema_path", lambda name: path)
    v._schema_registry.cache_clear()
    try:
        assert v._load_schema("fixture") == schema
        assert v.validate_against_schema({"value": 2}, schema) == []
        errors = v.validate_against_schema({"value": "not integer"}, {"$ref": schema["$id"]})
        assert len(errors) == 1 and errors[0].startswith("value:")
    finally:
        v._schema_registry.cache_clear()


def test_function_file_schema_and_print_contract(monkeypatch, schema_boundary, capsys):
    data = {"id": "OCF-FND-999", "slug": "fixture", "invalid": True}
    monkeypatch.setattr(v, "load_yaml_file", lambda path: data)
    result = v.validate_function_file(Path("fixture.yaml"))
    assert codes(result) == {"schema"}
    assert v.print_result(result) == 1 and "1 errors" in capsys.readouterr().out
    data["invalid"] = False
    assert v.print_result(v.validate_function_file(Path("fixture.yaml"))) == 0


def test_proposals_skip_prose_and_readme_but_flag_duplicate_structured_ids(
    monkeypatch, schema_boundary
):
    paths = [
        Path("README.md"),
        Path("draft/prose.md"),
        Path("a.yaml"),
        Path("b.yml"),
        Path("no-id.yaml"),
    ]
    monkeypatch.setattr(v, "discover_proposal_files", lambda: paths)
    monkeypatch.setattr(
        v,
        "load_yaml_file",
        lambda path: {"invalid": True, "id": "OCFP-9999"} if path.name != "no-id.yaml" else {},
    )
    assert codes(v.validate_proposals()) == {"proposal-schema", "duplicate-proposal-id"}
    monkeypatch.setattr(v, "discover_proposal_files", lambda: [])
    assert v.validate_proposals().ok


def test_audio_background_and_voice_profile_wrappers_aggregate_findings(
    monkeypatch, schema_boundary
):
    paths = [Path("a.yaml"), Path("b.yaml"), Path("missing-id.yaml")]
    monkeypatch.setattr(indexes, "discover_audio_manifests", lambda: paths)
    monkeypatch.setattr(v, "discover_background_manifests", lambda: paths)
    monkeypatch.setattr(v, "discover_voice_profiles", lambda: paths)
    monkeypatch.setattr(
        v,
        "load_yaml_file",
        lambda path: (
            {"id": "fixture", "slug": "same", "invalid": True}
            if path.name != "missing-id.yaml"
            else {}
        ),
    )
    monkeypatch.setattr(
        v,
        "load_voice_profiles",
        lambda: [{"id": "fixture", "slug": "same"}, {"id": "other", "slug": "same"}],
    )
    assert "audio-schema" in codes(v.validate_audio_manifests())
    assert "background-schema" in codes(v.validate_background_manifests())
    assert {"voice-schema", "duplicate-voice-id", "duplicate-voice-slug"} <= codes(
        v.validate_voice_profiles()
    )
    monkeypatch.setattr(v, "discover_voice_profiles", lambda: [])
    assert v.validate_voice_profiles().ok


def test_timed_schema_failure_is_diagnostic_not_shape_crash(monkeypatch, schema_boundary):
    monkeypatch.setattr(v, "LocaleCatalog", lambda: object())
    doc = {"invalid": True, "timeline": [{"id": "a", "after": []}]}
    assert "timed-schema" in codes(v.validate_timed_transcript(doc, Path("fixture")))
    doc["invalid"] = False
    with pytest.raises(TypeError):
        v.validate_timed_transcript(doc, Path("fixture"))
    # An interpretable schema error still reports the actual timeline problem.
    doc = {"invalid": True, "timeline": [{"id": "a", "after": "missing"}]}
    monkeypatch.setattr(v, "validate_narration_usage", lambda *a: v.ValidationResult())
    monkeypatch.setattr(v, "validate_narration_hygiene", lambda *a: v.ValidationResult())
    assert {"timed-schema", "timed-timeline"} <= codes(
        v.validate_timed_transcript(doc, Path("fixture"))
    )


def test_timed_file_and_collection_delegation(monkeypatch, schema_boundary):
    document = {"timeline": [{"id": "a", "at": 0, "text": "fixture"}]}
    monkeypatch.setattr(v, "load_yaml_file", lambda path: document)
    monkeypatch.setattr(v, "LocaleCatalog", lambda: object())
    monkeypatch.setattr(v, "validate_narration_usage", lambda *a: finding("usage"))
    monkeypatch.setattr(v, "validate_narration_hygiene", lambda *a: finding("hygiene"))
    assert codes(v.validate_timed_transcript_file(Path("fixture"))) == {"usage", "hygiene"}
    monkeypatch.setattr(v, "discover_timed_transcripts", lambda: [Path("fixture")])
    assert {"timed-count", "usage", "hygiene"} == codes(v.validate_timed_transcripts())


@pytest.mark.parametrize("case", ["load-error", "initial", "unknown-preset", "valid"])
def test_dsp_profile_validation_keeps_unknown_selections_explicit(monkeypatch, tmp_path, case):
    (tmp_path / "profile.yaml").write_text("synthetic path")
    monkeypatch.setattr(semantic_dsp, "PROFILES_DIR", tmp_path)

    def load(path):
        if case == "load-error":
            raise OCFError("bad profile")
        return {
            "initial_state": "unknown" if case == "initial" else "ordinary",
            "states": {
                "ordinary": {"mode": "disabled"},
                "focus": {"mode": "preset", "preset": "declared"},
            },
        }

    monkeypatch.setattr(semantic_dsp, "load_profile", load)
    monkeypatch.setattr(
        audio_build,
        "_resolve_background_manifest",
        lambda id: None if case == "unknown-preset" else {},
    )
    if case == "valid":
        monkeypatch.setattr(audio_build, "_resolve_background_manifest", lambda id: {"id": id})
    result = v.validate_semantic_dsp_profiles()
    assert result.ok is (case == "valid")
    if case != "valid":
        assert codes(result) == {"semantic-dsp-profile"}


def test_library_validation_strips_slot_controls_on_copy_and_retains_failures(
    monkeypatch, tmp_path
):
    for folder in ("stages", "cues", "templates"):
        (tmp_path / folder).mkdir()
    for folder in ("stages", "cues"):
        (tmp_path / folder / "bad.yaml").write_text("synthetic path")
    for name in ("draft", "reviewed", "bad"):
        (tmp_path / "templates" / f"{name}.yaml").write_text("synthetic path")
    monkeypatch.setattr(semantics, "STAGES_DIR", tmp_path / "stages")
    monkeypatch.setattr(semantics, "CUE_PROFILES_DIR", tmp_path / "cues")
    monkeypatch.setattr(session, "TEMPLATES_DIR", tmp_path / "templates")

    def invalid(ref):
        raise OCFError("invalid record")

    monkeypatch.setattr(semantics, "load_stage", invalid)
    monkeypatch.setattr(semantics, "load_cue_profile", invalid)
    original = {
        "name": "Fixture",
        "content_status": "architecture-draft",
        "slots": {"required": ["main"]},
        "sections": [
            {"id": "body", "slot": "main", "from_slot": "main", "repeat": 2, "pace": "even-span"}
        ],
    }
    before = deepcopy(original)

    def load(ref):
        if Path(ref).stem == "bad":
            raise OCFError("bad template")
        return original if Path(ref).stem == "draft" else {**original, "content_status": "reviewed"}

    monkeypatch.setattr(session, "load_template", load)
    composed = []
    monkeypatch.setattr(
        session, "compose", lambda data, *a, **kw: composed.append(data) or {"timeline": []}
    )
    monkeypatch.setattr(transcript, "resolve_timeline", lambda data: ([], ["timeline problem"]))
    monkeypatch.setattr(semantics, "bind_document_cues", lambda data: [])
    monkeypatch.setattr(v, "LocaleCatalog", lambda: object())
    monkeypatch.setattr(v, "validate_narration_usage", lambda *a: finding("usage"))

    def hygiene(*a):
        result = finding("narration-required")
        result.extend(finding("real-structural-error"))
        return result

    monkeypatch.setattr(v, "validate_narration_hygiene", hygiene)
    result = v.validate_session_library()
    assert {
        "stage-invalid",
        "cue-profile-invalid",
        "template-invalid",
        "template-timeline",
        "template-narration-pending",
        "usage",
        "real-structural-error",
    } <= codes(result)
    assert original == before
    assert all(
        data["slots"] == {"required": [], "optional": []} and data["sections"] == [{"id": "body"}]
        for data in composed
    )
    assert sum(issue.code == "narration-required" for issue in result.issues) == 1


def test_validate_all_aggregates_owned_passes_and_registry_errors(monkeypatch):
    record = function_from_dict({"id": "OCF-FND-999", "slug": "fixture"}, Path("fixture"))
    monkeypatch.setattr(v, "load_all_functions", lambda: [record])
    monkeypatch.setattr(v, "validate_function_schema", lambda record: finding("schema"))
    monkeypatch.setattr(v, "validate_command_rules", lambda record: finding("command"))
    passes = (
        "validate_collection",
        "validate_legacy_invariants",
        "validate_proposals",
        "validate_audio_manifests",
        "validate_background_manifests",
        "validate_timed_transcripts",
        "validate_voice_profiles",
        "validate_locale_packs",
        "validate_session_library",
        "validate_semantic_dsp_profiles",
    )
    for name in passes:
        monkeypatch.setattr(v, name, lambda code=name: finding(code))
    monkeypatch.setattr(content, "validate_library", lambda: ["content error"])

    def bad_registry():
        raise OCFError("registry error")

    monkeypatch.setattr(voice_registry, "load_registry", bad_registry)
    assert set(passes) | {"schema", "command", "function-content", "voice-registry"} == codes(
        v.validate_all()
    )
    monkeypatch.setattr(voice_registry, "load_registry", lambda: [])
    monkeypatch.setattr(content, "validate_library", lambda: [])
    monkeypatch.setattr(v, "load_all_functions", lambda: [])
    assert "voice-registry" not in codes(v.validate_all())
