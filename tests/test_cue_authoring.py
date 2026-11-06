"""Cue-template validation stays inside the canonical locale function file."""

import pytest
import yaml
from authoring_fixtures import seed, write
from ocf_tools.authoring import AuthoringService
from ocf_tools.utils import yaml_safe_load

pytestmark = pytest.mark.integration


def test_unsaved_canonical_narration_template_uses_local_function_cues(tmp_path):
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
    service = AuthoringService(tmp_path)

    assert not any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    changed = yaml_safe_load(function.read_text(encoding="utf-8"))
    changed["entries"][key]["cue_template"]["allowed"] = ["cue.release"]
    service.update(function.as_uri(), yaml.safe_dump(changed, sort_keys=False))
    assert any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    service.close(function.as_uri())
    assert not any(item.code == "ocf.cue-template" for item in service.analyze(function.as_uri()))
    assert function.read_bytes() == before
