"""Version selection, immutable writes, membership and exact dependency failures."""

import json

import pytest
from ocf_tools import audio_defaults as defaults
from ocf_tools import semantic_dsp, session
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(defaults, "REPO_ROOT", tmp_path)

    def profile(identifier):
        return {"id": identifier, "version": "1.0.0"}

    monkeypatch.setattr(semantic_dsp, "load_profile", profile)
    monkeypatch.setattr(session, "load_template", profile)
    monkeypatch.setattr(session, "load_pacing_profile", profile)
    source = tmp_path / "content.yaml"
    source.write_text("original content\n")
    old_path = tmp_path / "audio/defaults" / (defaults.PREVIOUS_BASELINE_ID + ".json")
    old_path.parent.mkdir(parents=True)
    old = defaults.configuration_lock(["content.yaml"], baseline_id=defaults.PREVIOUS_BASELINE_ID)
    old_path.write_text(json.dumps(old))
    return source, old_path, old_path.with_name(defaults.BASELINE_ID + ".json")


def test_explicit_successor_and_predecessor_verify_matching_versions(monkeypatch, tmp_path):
    source, old, new = setup(monkeypatch, tmp_path)
    original = old.read_bytes()
    defaults.create_lock(new, dependency_names=["content.yaml"])
    assert defaults.check_lock(old)["version"] == "1.0.0"
    assert defaults.check_lock(new)["version"] == defaults.BASELINE_VERSIONS[defaults.BASELINE_ID]
    assert defaults.check_lock(new)["profiles"] == defaults.check_lock(old)["profiles"]
    assert old.read_bytes() == original
    with pytest.raises(OCFError, match="immutable"):
        defaults.create_lock(old, baseline_id=defaults.PREVIOUS_BASELINE_ID)
    source.write_text("changed content\n")
    with pytest.raises(OCFError, match="stale"):
        defaults.check_lock(new)


@pytest.mark.parametrize("mutation", ["identity", "unknown", "missing-dependency", "profile"])
def test_successor_rejects_forged_or_incomplete_lock(monkeypatch, tmp_path, mutation):
    source, old, new = setup(monkeypatch, tmp_path)
    defaults.create_lock(new, dependency_names=["content.yaml"])
    data = json.loads(new.read_text())
    if mutation == "identity":
        data["id"] = defaults.PREVIOUS_BASELINE_ID
    elif mutation == "unknown":
        data["id"] = "OCF-AUDIO-DEFAULTS-HPLUS-999"
        new = new.with_name(data["id"] + ".json")
    elif mutation == "missing-dependency":
        data["files"] = {}
    else:
        data["profiles"]["dsp"]["version"] = "changed"
    new.write_text(json.dumps(data))
    with pytest.raises(OCFError):
        defaults.check_lock(new)


@pytest.mark.parametrize("dependency", ["../escape.yaml", "/absolute.yaml"])
def test_dependency_containment_rejects_escape_before_hashing(monkeypatch, tmp_path, dependency):
    setup(monkeypatch, tmp_path)
    with pytest.raises(OCFError, match="escapes repository"):
        defaults.configuration_lock([dependency])


def test_create_rejects_mismatched_identity_path_without_output(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    target = tmp_path / "wrong.json"
    with pytest.raises(OCFError, match="identity/path mismatch"):
        defaults.create_lock(target)
    assert not target.exists()


def test_atomic_immutable_write_refuses_a_racing_creator(monkeypatch, tmp_path):
    source, old, new = setup(monkeypatch, tmp_path)
    original_writer = defaults.write_text_atomic

    def competing_writer(path, text, **kwargs):
        path.write_text("concurrent human data\n")
        return original_writer(path, text, **kwargs)

    monkeypatch.setattr(defaults, "write_text_atomic", competing_writer)
    with pytest.raises(OCFError):
        defaults.create_lock(new, dependency_names=["content.yaml"])
    assert new.read_text() == "concurrent human data\n"
