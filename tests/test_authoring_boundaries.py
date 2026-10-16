"""Synthetic authoring-provider contracts, independent of canonical repository data."""

import json

import pytest
from ocf_tools import authoring
from ocf_tools.authoring import AuthoringService, Document, Span, schema_at
from ocf_tools.utils import OCFError, yaml_safe_dump

pytestmark = pytest.mark.unit


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml_safe_dump(data) if path.suffix != ".json" else json.dumps(data), encoding="utf-8"
    )
    return path


@pytest.fixture
def source(tmp_path):
    put(
        tmp_path,
        "functions/example.yaml",
        {
            "id": "OCF-TST-999",
            "slug": "example",
            "canonical": {"name": "Original fixture", "command": {"primary": "PLUS-EXAMPLE"}},
            "lifecycle": {},
            "commands": [
                {"id": "OCF-CMD-TST-999-PRIMARY", "role": "primary", "designation": "canonical"}
            ],
        },
    )
    put(
        tmp_path,
        "locales/en-US/manifest.yaml",
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "language_name": "English",
            "status": "canonical",
            "semantic_version": "1.0.0",
            "resources": [
                {"file": "narration.yaml", "domain": "narration"},
                {"file": "ui.yaml", "domain": "ui"},
            ],
        },
    )
    put(
        tmp_path,
        "locales/en-US/narration.yaml",
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "narration",
            "entries": {
                "example.spoken": {
                    "text": "Original fixture {count}.",
                    "variables": ["count"],
                    "status": "draft",
                    "version": "1.0.0",
                }
            },
        },
    )
    put(
        tmp_path,
        "locales/en-US/ui.yaml",
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "ui",
            "entries": {"example.title": "Original fixture title"},
        },
    )
    for folder, name, identifier in (
        ("audio/templates/sessions", "session", "OCF-TPL-SESSION-EXAMPLE-001"),
        ("audio/templates/pacing", "pacing", "OCF-PACING-EXAMPLE-001"),
        ("audio/templates/stages", "stage", "OCF-TPL-STAGE-EXAMPLE-001"),
        ("audio/background/state-profiles", "dsp", "OCF-DSP-EXAMPLE-001"),
        ("audio/background/manifests", "background", "OCF-BG-9999"),
        ("audio/voices/profiles", "voice", "OCF-VOICE-9999"),
        ("audio/manifests", "implementation", "OCF-AUDIO-9999"),
    ):
        put(tmp_path, f"{folder}/{name}.yaml", {"id": identifier, "name": name})
    put(tmp_path, "brand/themes/example.json", {"id": "ocf-example", "name": "Example"})
    script = put(
        tmp_path,
        "audio/scripts/example.yaml",
        {
            "schema_version": "1.0",
            "id": "original-example",
            "title": "Original test fixture",
            "function_id": "OCF-TST-999",
            "locale": "en-US",
            "source": {"format": "manual", "filename": "synthetic-original"},
            "timeline": [
                {
                    "id": "spoken",
                    "at": "0:00.000",
                    "narration_key": "example.spoken",
                    "variables": {"count": 2},
                }
            ],
        },
    )
    return AuthoringService(tmp_path), script


def test_synthetic_timeline_uses_locale_and_commands_without_repository_records(source):
    service, path = source
    assert service.analyze(path.as_uri()) == []
    assert service.catalog() is service.catalog()
    service.update(path.as_uri(), path.read_text().replace("example.spoken", "example.missing"))
    findings = service.analyze(path.as_uri())
    assert any(item.code == "narration-unknown-key" for item in findings)
    service.close(path.as_uri())
    assert service.analyze(path.as_uri()) == []
    assert service.records()[0].id == "OCF-TST-999"


@pytest.mark.parametrize(
    "field,prefix,expected",
    [
        ("function_id", "OCF-TST-", "OCF-TST-999"),
        ("narration_key", "example.", "example.spoken"),
        ("title_key", "example.", "example.title"),
        ("template", "OCF-TPL-", "OCF-TPL-SESSION-EXAMPLE-001"),
        ("pacing_profile", "OCF-PACING-", "OCF-PACING-EXAMPLE-001"),
        ("stage", "OCF-TPL-STAGE-", "OCF-TPL-STAGE-EXAMPLE-001"),
        ("dsp_profile", "OCF-DSP-", "OCF-DSP-EXAMPLE-001"),
        ("voice_profile", "OCF-VOICE-", "OCF-VOICE-9999"),
        ("preset", "OCF-BG-", "OCF-BG-9999"),
        ("artwork_theme", "ocf-", "ocf-example"),
        ("command_id", "OCF-CMD-", "OCF-CMD-TST-999-PRIMARY"),
        ("locale", "en", "en-US"),
    ],
)
def test_completions_are_typed_and_references_navigate_to_their_owner(
    source, field, prefix, expected
):
    service, script = source
    text = f"{field}: {prefix}"
    service.update(script.as_uri(), text)
    _doc, _span, rows = service.completions(script.as_uri(), len(text))
    assert expected in {row["label"] for row in rows}
    service.update(script.as_uri(), f"{field}: {expected}")
    _doc, _span, definitions = service.definitions_at(script.as_uri(), len(field) + 3)
    assert definitions and definitions[0].name == expected
    assert all(item.path.is_relative_to(service.root) for item in definitions)


def test_schema_properties_enums_and_local_event_navigation(source):
    service, script = source
    service.update(script.as_uri(), "ti")
    _doc, _span, rows = service.completions(script.as_uri(), 2)
    assert "timeline" in {row["label"] for row in rows}
    plan = service.root / "overrides.json"
    service.associations["overrides.json"] = "session-overrides.schema.json"
    service.update(plan.as_uri(), '{"ending": "wa"}')
    _doc, _span, rows = service.completions(plan.as_uri(), len('{"ending": "wa'))
    assert rows[0]["label"] == "waking"
    service.update(
        script.as_uri(), "timeline:\n  - id: earlier\n  - id: later\n    after: earlier\n"
    )
    _doc, _span, definitions = service.definitions_at(
        script.as_uri(), service.overlays[authoring.path_key(script)][1].rindex("earlier") + 2
    )
    assert definitions[0].kind == "local-event"
    with pytest.raises(OCFError, match="composition-aware"):
        service.rename_preview(
            script.as_uri(),
            service.overlays[authoring.path_key(script)][1].rindex("earlier"),
            "changed",
        )


def test_reference_search_respects_declaration_filter_and_preview_bounds(source):
    service, script = source
    code = put(service.root, "scripts/ocf_tools/literal.py", {})
    code.write_text('VALUE = "OCF-TST-999"\n', encoding="utf-8")
    refs = service.references("OCF-TST-999", include_declarations=False)
    assert any(doc.path == code for doc, _span in refs)
    assert not any(doc.path.name == "example.yaml" and span.path == ("id",) for doc, span in refs)
    at = script.read_text().index("OCF-TST-999")
    result = service.rename_preview(script.as_uri(), at, "OCF-TST-999", limit=1)
    assert result["collision"] is True and result["next_offset"] == 1
    assert result["automatic_rename"] is False
    for kwargs in ({"limit": 0}, {"offset": -1}, {"limit": True}):
        with pytest.raises(OCFError, match="pagination"):
            service.rename_preview(script.as_uri(), at, "new", **kwargs)


def test_unsaved_new_resources_duplicate_pack_keys_and_index_invalidation(source):
    service, script = source
    service.refresh()
    count = service.refreshes
    service.refresh()
    assert service.refreshes == count
    ui = service.root / "locales/en-US/ui.yaml"
    service.update(ui.as_uri(), ui.read_text().replace("example.title", "example.spoken"))
    assert any("duplicate key" in problem for problem in service.catalog().problems)
    service.close(ui.as_uri())
    new = service.root / "audio/voices/profiles/unsaved.yaml"
    service.update(new.as_uri(), "id: OCF-VOICE-9998\nname: Unsaved\n")
    service.refresh()
    assert service.definitions["OCF-VOICE-9998"][0].path == new
    service.close(new.as_uri())
    service.refresh()
    assert "OCF-VOICE-9998" not in service.definitions


def test_bounded_reads_open_buffers_and_file_limits_fail_explicitly(source, monkeypatch):
    service, path = source
    reader = service._reader()
    for _ in range(32):
        reader(path)
    with pytest.raises(OCFError, match="32-read"):
        reader(path)
    monkeypatch.setattr(authoring, "MAX_FILES", 1)
    with pytest.raises(OCFError, match="1500-file"):
        service.refresh()
    service.overlays = {str(i): (path, "") for i in range(100)}
    with pytest.raises(OCFError, match="100 open"):
        service.update(path.as_uri(), "new")


def test_schema_pointer_escaping_duplicate_json_and_parse_positions(tmp_path):
    path = tmp_path / "custom.json"
    service = AuthoringService(
        tmp_path, associations={"custom.json": "locale-resource.schema.json"}
    )
    service.update(path.as_uri(), '{"locale":"en-US", "domain":"ui", "entries":{"bad/key":12}}')
    findings = service.analyze(path.as_uri())
    assert any("bad~1key" in item.pointer for item in findings)
    assert Document(path, '{"a":1,"a":2}').diagnostics[0].code == "ocf.duplicate-key"
    doc = Document(path, '{"value": }')
    assert doc.diagnostics[0].start > 0
    assert doc.span(("unknown",)).start == 0
    assert Span((), "", 0, 1).key is False


def test_local_schema_refs_resolve_for_completion_without_remote_retrieval():
    schema = {
        "definitions": {"entry": {"properties": {"name": {"type": "string"}}}},
        "properties": {"items": {"type": "array", "items": {"$ref": "#/definitions/entry"}}},
    }
    assert schema_at(schema, ("items", 0, "name"))["type"] == "string"
    assert schema_at({"$ref": "https://example.invalid/unregistered.json"}, ()) == {}
