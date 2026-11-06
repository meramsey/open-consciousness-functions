"""Cue-template editor features resolve only canonical locale function cues."""

import json

import pytest
import yaml
from authoring_fixtures import seed, write
from ocf_tools.authoring import AuthoringService
from ocf_tools.utils import yaml_safe_load

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("serialization", ["yaml", "json"])
def test_unsaved_canonical_narration_template_uses_local_function_cues(tmp_path, serialization):
    seed(tmp_path)
    function = tmp_path / "locales/en-US/OCF-FND-002-Focus.yaml"
    data = yaml_safe_load(function.read_text(encoding="utf-8"))
    key = "hplus.function.ocf-fnd-002.function-body"
    data["entries"][key].update(
        text="😀 Begin {{ cue.primary }}. Repeat {{ cue.primary }}.",
        status="reviewed",
        cue_template={"function_id": "OCF-FND-002", "allowed": ["cue.primary"]},
    )
    write(function, data)
    before = function.read_bytes()
    if serialization == "json":
        function.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        before = function.read_bytes()
    service = AuthoringService(tmp_path)

    assert not any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    text = function.read_text(encoding="utf-8")
    offset = text.index("{{ cue.primary") + len("{{ cue.pr")
    _doc, span, choices = service.completions(function.as_uri(), offset)
    assert text[span.start : span.end] == "cue.primary"
    assert "cue.primary" in {item["label"] for item in choices}
    _doc, _span, definitions = service.definitions_at(function.as_uri(), offset)
    assert definitions and definitions[0].path == function
    assert "Plus Focus" in definitions[0].description

    changed = yaml_safe_load(function.read_text(encoding="utf-8"))
    changed["entries"][key]["cue_template"]["allowed"] = ["cue.release"]
    service.update(function.as_uri(), yaml.safe_dump(changed, sort_keys=False))
    assert any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    service.close(function.as_uri())
    assert not any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))

    changed_owner = yaml_safe_load(function.read_text(encoding="utf-8"))
    changed_owner["activation"]["spoken_cue"]["text"] = "Unapproved changed cue"
    service.update(function.as_uri(), yaml.safe_dump(changed_owner, sort_keys=False))
    assert any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    service.close(function.as_uri())
    assert not any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    assert function.read_bytes() == before
