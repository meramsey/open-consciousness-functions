"""Canonical per-function content layers must be authoritative, never inferred."""

from types import SimpleNamespace

import pytest
from ocf_tools import content
from ocf_tools.models import FunctionRecord
from ocf_tools.utils import OCFError


class MockCatalog:
    def __init__(self, key):
        self.canonical = {key: SimpleNamespace(domain="narration")}


def synthetic_record(record_id: str, with_narration: bool = False):
    content_payload = {
        "evidence": {
            "sources": [
                {
                    "sha256": "a" * 64,
                    "path": "mock.txt",
                    "evidence_class": "reconstructed_mockup",
                    "authentication": "unverified",
                    "completeness": "n/a",
                }
            ],
            "observations": [
                {
                    "id": "obs1",
                    "kind": "source-fact",
                    "scope": "document",
                    "source_sha256": "a" * 64,
                    "category": "cat",
                    "line_candidates": [1],
                    "confidence": "high",
                }
            ],
            "questions": [],
        },
        "specifications": {
            "metadata_ref": "canonical-function-record",
            "command_ref": "canonical.command",
            "extraction_status": "partial",
            "maturity": "draft",
            "human_review": "required",
            "states": {"status": "unknown", "required": [], "preferred": []},
            "preparation": [],
            "blocks": {
                "purpose": {"status": "unknown", "operations": [], "evidence_refs": []},
                "opener": {"status": "unknown", "operations": [], "evidence_refs": []},
                "main": {"status": "unknown", "operations": [], "evidence_refs": []},
                "association": {"status": "unknown", "operations": [], "evidence_refs": []},
                "rehearsal": {"status": "unknown", "operations": [], "evidence_refs": []},
                "future_use": {"status": "unknown", "operations": [], "evidence_refs": []},
                "suspend_cancel_reset": {
                    "status": "unknown",
                    "operations": [],
                    "evidence_refs": [],
                },
                "closer": {"status": "unknown", "operations": [], "evidence_refs": []},
                "consolidation": {"status": "unknown", "operations": [], "evidence_refs": []},
                "handoff": {"status": "unknown", "operations": [], "evidence_refs": []},
                "safety_claims": {"status": "unknown", "operations": [], "evidence_refs": []},
            },
            "questions": [],
        },
        "decisions": {"decisions": []},
        "bindings": {
            "session_templates": [],
            "narration_resources": [],
            "voice_sources": None,
            "duration": None,
        },
    }
    data = {"content": content_payload}
    if with_narration:
        data["narration"] = {
            "sequence": [{"key": "relax.body", "role": "function-body", "repetitions": 2}]
        }
    return FunctionRecord(record_id, record_id.lower(), "path/to/record.yaml", data)


def test_canonical_load_reads_only_the_canonical_record(monkeypatch, tmp_path):
    record = synthetic_record("OCF-FND-004")
    legacy = tmp_path / "function-content"
    for layer in content.LAYERS:
        (legacy / layer).mkdir(parents=True)
        (legacy / layer / f"{record.id}.yaml").write_text(
            "function_id: injected\n", encoding="utf-8"
        )
    monkeypatch.setattr(content, "CONTENT_DIR", legacy)

    from ocf_tools import indexes

    monkeypatch.setattr(indexes, "load_function_by_id", lambda *_: record)
    layers = content.load_layers(record.id)

    assert set(layers) <= set(content.LAYERS)
    assert all(payload["schema_version"] == "1.0" for payload in layers.values())
    assert all(payload["function_id"] == record.id for payload in layers.values())


def test_canonical_load_returns_a_copy_isolated_from_the_record(monkeypatch):
    record = synthetic_record("OCF-FND-004", with_narration=True)
    monkeypatch.setattr("ocf_tools.locale.LocaleCatalog", lambda: MockCatalog("relax.body"))
    from ocf_tools import indexes

    monkeypatch.setattr(indexes, "load_function_by_id", lambda *_: record)
    layers = content.load_layers(record.id)

    layers["evidence"]["injected"] = True
    layers["bindings"]["narration_plan"]["sequence"].pop()

    assert record.data["content"]["evidence"].get("injected") is None
    assert record.data["narration"] != layers["bindings"]["narration_plan"]


def test_canonical_load_injects_narration_plan_from_the_function_record(monkeypatch):
    record = synthetic_record("OCF-FND-004", with_narration=True)
    monkeypatch.setattr("ocf_tools.locale.LocaleCatalog", lambda: MockCatalog("relax.body"))
    from ocf_tools import indexes

    monkeypatch.setattr(indexes, "load_function_by_id", lambda *_: record)
    layers = content.load_layers(record.id)
    assert layers["bindings"]["narration_plan"] == record.data["narration"]
    assert "narration_plan" not in record.data["content"]["bindings"]


def test_missing_canonical_record_never_falls_back_to_legacy_files(monkeypatch, tmp_path):
    legacy = tmp_path / "function-content"
    for layer in content.LAYERS:
        (legacy / layer).mkdir(parents=True)
        (legacy / layer / "OCF-XXX-999.yaml").write_text(
            "schema_version: '1.0'\nfunction_id: OCF-XXX-999\n", encoding="utf-8"
        )
    monkeypatch.setattr(content, "CONTENT_DIR", legacy)
    from ocf_tools import indexes

    monkeypatch.setattr(indexes, "load_function_by_id", lambda *_: None)
    with pytest.raises(OCFError, match="unavailable canonical function: OCF-XXX-999"):
        content.load_layers("OCF-XXX-999")


def test_invalid_provenance_in_canonical_content_fails_validation(monkeypatch):
    record = synthetic_record("OCF-FND-004")
    record.data["content"]["evidence"]["sources"][0]["authentication"] = "authenticated"
    record.data["content"]["evidence"]["sources"][0]["authentication_record"] = "auth-1"
    record.data["content"]["evidence"]["sources"][0]["evidence_class"] = "reconstructed_mockup"
    from ocf_tools import indexes

    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(indexes, "load_function_by_id", lambda *_: record)
    try:
        with pytest.raises(OCFError):
            content.load_layers(record.id)
    finally:
        monkeypatched.undo()


def test_validate_library_reports_stray_alternative_layer_files(monkeypatch, tmp_path):
    stray = tmp_path / "function-content"
    (stray / "evidence").mkdir(parents=True)
    stray_path = stray / "evidence" / "OCF-FND-004.yaml"
    stray_path.write_text("function_id: stray\n", encoding="utf-8")
    monkeypatch.setattr(content, "CONTENT_DIR", stray)
    monkeypatch.setattr(content, "load_all_functions", lambda: [synthetic_record("OCF-FND-004")])
    monkeypatch.setattr(content, "load_layers", lambda *_args, **_kw: {})
    errors = content.validate_library()
    assert errors == [f"alternative function content layer: {stray_path}"]
