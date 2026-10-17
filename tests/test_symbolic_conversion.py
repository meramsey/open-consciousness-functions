"""Replay the structural authoring plan from retained pinned predecessor inputs."""

import json

import pytest
import yaml
from ocf_tools.models import FunctionRecord
from ocf_tools.utils import OCFError
from tools import convert_cue_templates as conversion


@pytest.mark.integration
def test_structural_converter_replays_pinned_sources_without_touching_runtime(
    monkeypatch, tmp_path
):
    from ocf_tools import indexes
    from tools import check_hplus_narration_integrity as integrity

    root = conversion.REPO_ROOT
    data = json.loads((root / conversion.RECORD).read_text(encoding="utf-8"))
    sources = dict(data["predecessor_files"])
    for path in (root / "function-content/bindings").glob("*.yaml"):
        sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    sources["audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"] = (
        root / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"
    ).read_text(encoding="utf-8")
    approval_name = "function-content/editorial/approved-title-cues-001.json"
    sources[approval_name] = (root / approval_name).read_text(encoding="utf-8")
    for name in (
        "locales/en-US/activation-cues.yaml",
        "locales/en-US/commands.yaml",
        "locales/en-US/manifest.yaml",
        "tests/fixtures/hplus-narration-text-baseline-002.json",
    ):
        sources[name] = (root / name).read_text(encoding="utf-8")
    records = []
    for name, raw in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8", newline="\n")
        if name.startswith("functions/"):
            doc = yaml.safe_load(raw)
            records.append(FunctionRecord(doc["id"], doc["slug"], path, doc))
    baseline = integrity.narration_texts()
    monkeypatch.setattr(conversion, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(conversion, "source", lambda name: sources[name])
    monkeypatch.setattr(indexes, "load_all_functions", lambda: records)
    monkeypatch.setattr(integrity, "narration_texts", lambda: baseline)
    result, outputs = conversion.prepare()
    assert result["resolved_baseline"] == data["resolved_baseline"]
    assert result["entries"] == data["entries"]
    assert result["files"] == data["files"]
    assert len(result["narration_bindings"]) == len(records) == 55
    for name, raw in sources.items():
        assert (tmp_path / name).read_text(encoding="utf-8") == raw
    # Ordinary dry-run computes the plan only, and the real write path creates
    # successor artifacts in this disposable fixture tree.
    assert conversion.main([]) == 0
    assert not (tmp_path / conversion.RECORD).exists()
    assert conversion.main(["--apply"]) == 0
    for name, content in outputs.items():
        assert (tmp_path / name).read_text(encoding="utf-8") == content
    with pytest.raises(OCFError, match="already exists"):
        conversion.prepare()
