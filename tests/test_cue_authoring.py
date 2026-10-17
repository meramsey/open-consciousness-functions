"""Unsaved function/resource overlays use the runtime resolver for cue navigation."""

import json

import pytest
from authoring_fixtures import seed, write
from ocf_tools.authoring import AuthoringService
from ocf_tools.utils import yaml_safe_dump, yaml_safe_load

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("format", ["yaml", "json"])
def test_embedded_completion_hover_definition_and_unsaved_errors_share_resolver(tmp_path, format):
    seed(tmp_path)
    function = tmp_path / "functions/foundation/focus.yaml"
    data = yaml_safe_load(function.read_text(encoding="utf-8"))
    command = next(row for row in data["commands"] if row["designation"] == "primary")
    command.update(spoken="Plus Focus", spoken_review="reviewed")
    command["localization"] = {"spoken_cue_key": "test.cue"}
    data["narration"] = {
        "sequence": [{"key": "test.guidance", "role": "function-body", "repetitions": 4}]
    }
    write(function, data)
    # Pack filenames remain .yaml; JSON is also valid YAML syntax.
    resource = tmp_path / "locales/en-US/narration.yaml"
    manifest_path = tmp_path / "locales/en-US/manifest.yaml"
    manifest = yaml_safe_load(manifest_path.read_text())
    manifest["resources"][0]["file"] = resource.name
    write(manifest_path, manifest)
    resource_data = {
        "schema_version": "1.0",
        "locale": "en-US",
        "domain": "narration",
        "entries": {
            "test.cue": {"text": "Plus Focus", "status": "reviewed", "version": "1.0.0"},
            "test.guidance": {
                "text": "😀 Begin {{ cue.primary }}.\nRepeat {{ cue.primary }}.",
                "status": "reviewed",
                "cue_template": {"function_id": "OCF-FND-002", "allowed": ["cue.primary"]},
            },
        },
    }
    write(resource, resource_data)
    if format == "json":
        resource.write_text(
            json.dumps(resource_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    service = AuthoringService(tmp_path)
    text = resource.read_text(encoding="utf-8")
    before = resource.read_bytes(), function.read_bytes()
    offset = text.index("{{ cue.primary") + len("{{ cue.pr")
    doc, span, rows = service.completions(resource.as_uri(), offset)
    assert "cue.primary" in {row["label"] for row in rows}
    assert text[span.start : span.end] == "cue.primary"
    _, _, definitions = service.definitions_at(resource.as_uri(), offset)
    assert definitions and definitions[0].path == function
    assert "Plus Focus" in definitions[0].description
    changed = text.replace("cue.primary", "cue.release")
    service.update(resource.as_uri(), changed)
    assert any(row.code == "ocf.cue-template" for row in service.analyze(resource.as_uri()))
    service.close(resource.as_uri())
    assert not any(row.code == "ocf.cue-template" for row in service.analyze(resource.as_uri()))
    function_data = deepcopy_data = json.loads(json.dumps(data))
    function_data["commands"][0]["spoken"] = "Unapproved changed cue"
    service.update(function.as_uri(), yaml_safe_dump(deepcopy_data))
    assert any(row.code == "ocf.cue-template" for row in service.analyze(resource.as_uri()))
    service.close(function.as_uri())
    assert not any(row.code == "ocf.cue-template" for row in service.analyze(resource.as_uri()))
    assert before == (resource.read_bytes(), function.read_bytes())
