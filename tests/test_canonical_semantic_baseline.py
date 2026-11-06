"""Path-free hash invariants for the approved single-source migration."""

import pytest
from ocf_tools.canonical_integrity import verify

pytestmark = pytest.mark.integration


def test_all_58_functions_preserve_approved_structure_and_narration():
    assert verify() == []


def test_identity_set_drift_fails_closed_before_per_function_projection(monkeypatch, tmp_path):
    from ocf_tools import canonical_integrity

    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"functions": {}}', encoding="utf-8")
    monkeypatch.setattr(canonical_integrity, "resources", lambda root: [])
    monkeypatch.setattr(canonical_integrity, "load_all_functions", lambda **kwargs: [])

    assert canonical_integrity.verify(tmp_path, baseline) == [
        "canonical semantic baseline identity set differs from the 58-function catalog"
    ]


def test_canonical_semantic_hash_drift_is_reported(monkeypatch, tmp_path):
    from ocf_tools import canonical_integrity

    current = verify()
    assert current == []
    import json

    baseline = json.loads(canonical_integrity.BASELINE.read_text(encoding="utf-8"))
    identity = next(iter(baseline["functions"]))
    baseline["functions"][identity]["commands_sha256"] = "0" * 64
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")

    assert canonical_integrity.verify(baseline_path=path) == [
        f"{identity}: canonical commands_sha256 differs from the approved baseline"
    ]
