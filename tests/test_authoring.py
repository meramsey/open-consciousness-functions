"""Shared authoring rules, unsaved buffers, navigation and containment contracts."""

import json

import pytest
from authoring_fixtures import seed, write
from ocf_tools import validators
from ocf_tools.authoring import MAX_BYTES, AuthoringService, Document, offset_at, position_at
from ocf_tools.utils import OCFError, yaml_safe_load


@pytest.fixture
def workspace(tmp_path):
    path = seed(tmp_path)
    return AuthoringService(tmp_path), path


@pytest.mark.integration
def test_unsaved_timeline_uses_existing_schema_locale_and_command_rules(workspace):
    service, path = workspace
    assert service.analyze(path.as_uri()) == []
    before = path.read_bytes()
    text = path.read_text(encoding="utf-8").replace("test.guidance", "test.missing")
    service.update(path.as_uri(), text)
    diagnostics = service.analyze(path.as_uri())
    assert any(item.code == "narration-unknown-key" for item in diagnostics)
    assert any(item.start > 0 for item in diagnostics)
    assert path.read_bytes() == before
    service.close(path.as_uri())
    assert service.analyze(path.as_uri()) == []


@pytest.mark.parametrize(
    "text",
    ["id: [", '{"id":', "value: .nan", "value: &cycle [*cycle]", "value: 2026-10-15", "1: value"],
)
@pytest.mark.unit
def test_malformed_nonfinite_cyclic_and_non_json_values_are_diagnostics(tmp_path, text):
    doc = Document(tmp_path / "example.yaml", text)
    assert doc.diagnostics and doc.diagnostics[0].code == "ocf.parse"


@pytest.mark.unit
def test_duplicate_keys_and_bounded_source_documents(tmp_path):
    assert (
        Document(tmp_path / "x.yaml", "id: one\nid: two\n").diagnostics[0].code
        == "ocf.duplicate-key"
    )
    assert (
        Document(tmp_path / "x.yaml", "x" * (MAX_BYTES + 1)).diagnostics[0].code
        == "ocf.document-size"
    )


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
@pytest.mark.unit
def test_unicode_positions_round_trip_with_crlf(encoding):
    text = "# 😀 first\r\nname: Café 😀\n"
    for offset, character in enumerate(text):
        if character in "\r\n":
            continue
        position = position_at(text, offset, encoding)
        assert offset_at(text, **position, encoding=encoding) == offset
    assert offset_at(text, 100, 0, encoding) == len(text)
    with pytest.raises(OCFError):
        offset_at(text, -1, 0)


@pytest.mark.integration
def test_function_resources_and_profiles_complete_and_navigate(workspace):
    service, path = workspace
    text = path.read_text(encoding="utf-8")
    at = text.index("OCF-FND-002") + len("OCF-FND-")
    _doc, _span, rows = service.completions(path.as_uri(), at)
    assert "OCF-FND-002" in {row["label"] for row in rows}
    _doc, _span, definitions = service.definitions_at(path.as_uri(), at)
    assert definitions[0].path.name == "focus.yaml"
    for field, prefix, expected in (
        ("narration_key", "test.", "test.guidance"),
        ("voice_profile", "OCF-VOICE-", "OCF-VOICE-0001"),
        ("pacing_profile", "OCF-PACING-", "OCF-PACING-TEST-001"),
        ("dsp_profile", "OCF-DSP-", "OCF-DSP-TEST-001"),
        ("template", "OCF-TPL-SESSION-", "OCF-TPL-SESSION-TEST-001"),
        ("locale", "en", "en-US"),
    ):
        service.update(path.as_uri(), f"{field}: {prefix}")
        _doc, _span, rows = service.completions(path.as_uri(), len(f"{field}: {prefix}"))
        assert expected in {row["label"] for row in rows}


@pytest.mark.integration
def test_inheritance_uses_unsaved_parents_and_the_same_loader_contracts(workspace):
    service, _path = workspace
    child = write(
        service.root / "audio/templates/sessions/child.yaml",
        {
            "schema_version": "1.0",
            "id": "OCF-TPL-SESSION-CHILD-001",
            "extends": "OCF-TPL-SESSION-TEST-001",
            "name": "Child",
        },
    )
    assert service.analyze(child.as_uri()) == []
    parent = service.root / "audio/templates/sessions/base.yaml"
    text = parent.read_text(encoding="utf-8").replace("reference-derived", "not-an-origin")
    service.update(parent.as_uri(), text)
    assert any(item.code == "ocf.configuration" for item in service.analyze(child.as_uri()))
    service.close(parent.as_uri())
    assert service.analyze(child.as_uri()) == []
    theme = write(
        service.root / "brand/themes/child.json",
        {"schema_version": "1.0", "id": "ocf-child", "version": "1.0", "extends": "base.json"},
    )
    assert service.analyze(theme.as_uri()) == []
    service.update(theme.as_uri(), json.dumps({"id": "ocf-child", "extends": "child.json"}))
    assert "cyclic" in service.analyze(theme.as_uri())[0].message


@pytest.mark.integration
def test_unknown_references_schema_ranges_and_literal_python_navigation(workspace):
    service, path = workspace
    text = path.read_text(encoding="utf-8").replace("OCF-FND-002", "OCF-FND-999")
    service.update(path.as_uri(), text)
    findings = service.analyze(path.as_uri())
    assert any(
        item.code == "ocf.unknown-reference" and "OCF-FND-999" in item.message for item in findings
    )
    service.close(path.as_uri())
    code = service.root / "scripts/ocf_tools/ref.py"
    code.parent.mkdir(parents=True)
    code.write_text('VALUE = "OCF-FND-002"\n', encoding="utf-8")
    assert any(doc.path == code for doc, _span in service.references("OCF-FND-002"))
    service.update(path.as_uri(), "schema_version: 17\n")
    assert any(item.code.startswith("ocf.schema.") for item in service.analyze(path.as_uri()))


@pytest.mark.integration
def test_index_cache_invalidation_does_not_stale_unsaved_or_saved_ids(workspace):
    service, path = workspace
    service.refresh()
    count = service.refreshes
    service.refresh()
    assert service.refreshes == count
    text = path.read_text(encoding="utf-8")
    service.update(path.as_uri(), text)
    service.refresh()
    count = service.refreshes
    service.update(path.as_uri(), text)
    service.refresh()
    assert service.refreshes == count
    voice = service.root / "audio/voices/profiles/fixture.yaml"
    voice.write_text(voice.read_text().replace("0001", "0002"), encoding="utf-8")
    service.refresh()
    assert "OCF-VOICE-0002" in service.definitions and "OCF-VOICE-0001" not in service.definitions


@pytest.mark.integration
def test_preview_is_paginated_read_only_and_never_an_editorial_edit(workspace):
    service, path = workspace
    before = {file: file.read_bytes() for file in service.root.rglob("*") if file.is_file()}
    at = path.read_text().index("OCF-FND-002")
    preview = service.rename_preview(path.as_uri(), at, "OCF-FND-099", limit=1)
    assert preview["status"] == "PROPOSED — NOT IMPLEMENTED"
    assert preview["automatic_rename"] is False and preview["read_only"] is True
    assert preview["total_references"] >= 2 and preview["next_offset"] == 1
    assert "changes" not in preview and "documentChanges" not in preview
    assert all(file.read_bytes() == data for file, data in before.items())
    with pytest.raises(OCFError):
        service.rename_preview(path.as_uri(), at, "bad\nname")


@pytest.mark.integration
def test_workspace_containment_and_remote_schema_refs_never_read_outside(workspace, tmp_path):
    service, path = workspace
    with pytest.raises(OCFError, match="workspace"):
        service.update((tmp_path.parent / "outside.yaml").as_uri(), "id: secret")
    external = service.root / "brand/themes/external.json"
    external.write_text('{"id":"ocf-external","extends":"../../../outside.json"}', encoding="utf-8")
    assert service.analyze(external.as_uri())[0].code == "ocf.configuration"
    generic = service.root / "unknown.json"
    service.update(generic.as_uri(), '{"$schema":"https://invalid.example/private-schema.json"}')
    assert "never fetches" in service.analyze(generic.as_uri())[0].message
    with pytest.raises(OCFError):
        service.path("https://invalid.example/file.yaml")


@pytest.mark.unit
def test_structured_schema_errors_are_the_existing_cli_engine():
    schema = {"type": "array", "items": {"type": "integer"}}
    errors = validators.schema_errors(["bad"] * 12, schema)
    assert [list(item.path) for item in errors] == [[index] for index in range(12)]
    assert validators.validate_against_schema(["bad"] * 12, schema) == [
        f"{index}: 'bad' is not of type 'integer'" for index in range(12)
    ]


@pytest.mark.unit
def test_merge_alias_expansion_is_rejected_before_construction(tmp_path, monkeypatch):
    from ocf_tools import authoring

    monkeypatch.setattr(authoring, "MAX_NODES", 40)

    def forbidden(_text):
        pytest.fail("merge construction must not run after the representation budget is exhausted")

    monkeypatch.setattr(authoring, "yaml_safe_load", forbidden)
    text = "a: &a {x: 1}\nb: &b {<<: [*a, *a, *a]}\nc: &c {<<: [*b, *b, *b]}\nd: {<<: [*c, *c, *c]}"
    doc = Document(tmp_path / "aliases.yaml", text)
    assert "complexity" in doc.diagnostics[0].message


@pytest.mark.integration
def test_unsaved_locale_resources_use_pack_validation_and_regional_fallback(workspace):
    service, path = workspace
    resource = service.root / "locales/en-US/narration.yaml"
    original = resource.read_text(encoding="utf-8")
    service.update(resource.as_uri(), original.replace("test.guidance", "test.revised"))
    assert any(item.code == "narration-unknown-key" for item in service.analyze(path.as_uri()))
    service.update(path.as_uri(), path.read_text().replace("test.guidance", "test.revised"))
    assert service.analyze(path.as_uri()) == []
    service.update(resource.as_uri(), original.replace("test.guidance", "INVALID KEY"))
    findings = service.analyze(resource.as_uri())
    assert any(item.code.startswith("ocf.schema.") for item in findings)
    assert any("invalid key" in problem for problem in service.catalog().problems)
    service.close(resource.as_uri())
    service.close(path.as_uri())
    # en-US can be served by en, but a different language cannot silently fall back.
    for file in (service.root / "locales/en-US").glob("*.yaml"):
        write(
            file.parent.parent / "en" / file.name,
            yaml_safe_load(file.read_text().replace("en-US", "en")),
        )
        file.unlink()
    assert service.analyze(path.as_uri()) == []
    service.update(path.as_uri(), path.read_text().replace("en-US", "es-MX"))
    assert any("locale" in item.message for item in service.analyze(path.as_uri()))


@pytest.mark.integration
def test_pacing_policy_paths_are_not_locale_ids_and_unknown_values_are_reported(workspace):
    service, _path = workspace
    parent = service.root / "audio/templates/sessions/base.yaml"
    data = yaml_safe_load(parent.read_text())
    data["sections"][0]["repeat_pacing_key"] = "repetitions.focus11"
    write(parent, data)
    # The canonical fixture profile defines repetitions.focus11.
    findings = service.analyze(parent.as_uri())
    assert not any("repetitions.focus11" in item.message for item in findings)
    service.update(
        parent.as_uri(), parent.read_text().replace("repetitions.focus11", "repetitions.missing")
    )
    assert any(item.code == "ocf.pacing-reference" for item in service.analyze(parent.as_uri()))


@pytest.mark.integration
def test_generated_shared_metadata_is_not_a_function_plan(workspace):
    service, _path = workspace
    path = write(
        service.root / "audio/session-plans/en-US/_shared.json",
        {"defaults_lock": {}, "profiles": {}},
    )
    findings = service.analyze(path.as_uri())
    assert [item.code for item in findings] == ["ocf.generated-document"]
    invalid_plan = write(path.parent / "OCF-FND-002.json", {})
    findings = service.analyze(invalid_plan.as_uri())
    assert any(item.code == "ocf.generated-document" for item in findings)
    assert any(item.code.startswith("ocf.schema.") for item in findings)


@pytest.mark.integration
def test_symlinked_sources_and_inherited_files_cannot_escape_workspace(workspace, tmp_path):
    service, _path = workspace
    outside = tmp_path.parent / "outside-theme.json"
    outside.write_text('{"id":"private-external"}', encoding="utf-8")
    link = service.root / "brand/themes/link.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    service.refresh()
    assert "private-external" not in service.definitions
    with pytest.raises(OCFError, match="escapes"):
        service.document(link)
