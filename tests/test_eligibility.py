import json

import pytest
from ocf_tools.eligibility import eligibility, migrate_bindings
from ocf_tools.paths import REPO_ROOT


def test_migration_preserves_sources_reviews_and_all_functions():
    report = json.loads(
        (REPO_ROOT / "docs/releases/OCF_TTS_ELIGIBILITY_MIGRATION.json").read_text()
    )
    assert report["total"] == report["tts_renderable"] == 55
    assert report["previous_source_available"] == 39
    assert report["previous_source_unavailable"] == 16
    assert all(
        r["human_review"] == "required" and not r["release_ready"] for r in report["functions"]
    )
    unavailable = next(
        r for r in report["functions"] if r["historical_source_availability"] == "unavailable"
    )
    current = eligibility(unavailable["function_id"])
    previous_reviews = unavailable["narration_review_status"]
    current_reviews = current.pop("narration_review_status")
    previous = dict(unavailable)
    previous.pop("narration_review_status")
    assert current == previous
    removed = {"hplus.shared.relaxation.torso", "hplus.shared.relaxation.legs"}
    assert previous_reviews.keys() - current_reviews.keys() == removed
    assert {key: current_reviews[key] for key in previous_reviews if key not in removed} == {
        key: value for key, value in previous_reviews.items() if key not in removed
    }
    assert {
        key: value for key, value in current_reviews.items() if key not in previous_reviews
    } == {
        key: "reviewed"
        for key in (
            "hplus.shared.focus20.close.ready",
            "hplus.shared.relaxation.support",
            "hplus.shared.relaxation.jaw-neck",
            "hplus.shared.relaxation.chest-breathing",
            "hplus.shared.relaxation.abdomen-lower-back",
            "hplus.shared.relaxation.hips-thighs",
            "hplus.shared.relaxation.lower-legs-feet",
            "hplus.shared.relaxation.whole-body-awareness",
        )
    }


def test_spoken_locale_missing_dependency_is_reported_without_cross_language_fallback():
    result = eligibility("OCF-FND-002", "es")
    assert not result["tts_renderable"]
    assert result["blockers"]
    assert not result["release_ready"]


def test_unknown_function_is_reported_without_claiming_source_or_renderability():
    result = eligibility("OCF-XXX-999")

    assert result["function_exists"] is False
    assert result["historical_source_availability"] is None
    assert result["tts_renderable"] is False
    assert result["release_ready"] is False
    assert result["blockers"]


def test_invalid_complete_plan_is_a_blocker_not_a_renderability_claim(monkeypatch):
    from ocf_tools import complete_session

    def invalid(*args, **kwargs):
        raise ValueError("malformed canonical plan")

    monkeypatch.setattr(complete_session, "build_complete_session_plan", invalid)
    result = eligibility("OCF-FND-002")

    assert result["tts_renderable"] is False
    assert result["timing_plan_available"] is False
    assert result["release_ready"] is False
    assert result["blockers"] == ["malformed canonical plan"]


def test_binding_migration_applies_only_canonical_plan_and_preserves_custom_template(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    import yaml
    from ocf_tools import content
    from ocf_tools import eligibility as service

    identity = "OCF-COG-001"
    path = tmp_path / "function.yaml"
    path.write_text(yaml.safe_dump({"function_id": identity, "content": {}}), encoding="utf-8")
    narration = {"sequence": [{"key": "function.body", "role": "function-body"}]}
    record = SimpleNamespace(
        id=identity,
        path=path,
        data={
            "narration": narration,
            "content": {
                "bindings": {
                    "default_session_template": "OCF-TPL-CUSTOM-001",
                    "session_templates": ["OCF-TPL-CUSTOM-001"],
                    "voice_sources": [],
                }
            },
        },
    )
    monkeypatch.setattr(service, "LocaleCatalog", lambda: object())
    monkeypatch.setattr(service, "load_function_by_id", lambda _: record)
    monkeypatch.setattr(content, "validate_layers", lambda *_: [])

    rows = service.migrate_bindings([identity], dry_run=False)
    result = yaml.safe_load(path.read_text(encoding="utf-8"))["content"]["bindings"]

    assert rows == [
        {
            "function_id": identity,
            "default_session_template": "OCF-TPL-CUSTOM-001",
            "dry_run": False,
        }
    ]
    assert result["default_session_template"] == "OCF-TPL-CUSTOM-001"
    assert result["voice_sources"] == ["tts"]
    assert "narration_plan" not in result


def test_binding_migration_rejects_synthesized_narration_before_any_write(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from ocf_tools import eligibility as service
    from ocf_tools.utils import OCFError

    path = tmp_path / "function.yaml"
    path.write_text("function_id: OCF-COG-001\n", encoding="utf-8")
    record = SimpleNamespace(id="OCF-COG-001", path=path, data={"content": {"bindings": None}})

    class Catalog:
        def resource(self, key, locale, **kwargs):
            return SimpleNamespace(text="local speech"), None

    monkeypatch.setattr(service, "LocaleCatalog", Catalog)
    monkeypatch.setattr(service, "load_function_by_id", lambda _: record)

    with pytest.raises(OCFError, match="canonical narration sequence is missing"):
        service.migrate_bindings([record.id], dry_run=False)
    assert path.read_text(encoding="utf-8") == "function_id: OCF-COG-001\n"


def test_binding_migration_never_substitutes_a_plan_for_missing_canonical_narration(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    from ocf_tools import eligibility as service
    from ocf_tools.utils import OCFError

    path = tmp_path / "function.yaml"
    path.write_text("function_id: OCF-COG-001\n", encoding="utf-8")
    binding = {
        "session_templates": [],
        "narration_resources": [],
        "voice_sources": ["tts"],
        "narration_plan": {"sequence": [{"key": "old.plan"}]},
    }
    record = SimpleNamespace(id="OCF-COG-001", path=path, data={"content": {"bindings": binding}})
    monkeypatch.setattr(service, "LocaleCatalog", lambda: object())
    monkeypatch.setattr(service, "load_function_by_id", lambda _: record)

    with pytest.raises(OCFError, match="canonical narration sequence is missing"):
        service.migrate_bindings([record.id])
    assert path.read_text(encoding="utf-8") == "function_id: OCF-COG-001\n"


def test_binding_migration_rejects_unknown_identity(monkeypatch):
    from ocf_tools import eligibility as service
    from ocf_tools.utils import OCFError

    monkeypatch.setattr(service, "LocaleCatalog", lambda: object())
    monkeypatch.setattr(service, "load_function_by_id", lambda _: None)

    with pytest.raises(OCFError, match="unknown function OCF-XXX-999"):
        service.migrate_bindings(["OCF-XXX-999"])


def test_binding_migration_rejects_empty_synthesized_locale_resource(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from ocf_tools import eligibility as service
    from ocf_tools.utils import OCFError

    path = tmp_path / "function.yaml"
    path.write_text("function_id: OCF-COG-001\n", encoding="utf-8")
    record = SimpleNamespace(id="OCF-COG-001", path=path, data={"content": {"bindings": {}}})

    class Catalog:
        def resource(self, key, locale, **kwargs):
            return SimpleNamespace(text="   "), None

    monkeypatch.setattr(service, "LocaleCatalog", Catalog)
    monkeypatch.setattr(service, "load_function_by_id", lambda _: record)

    with pytest.raises(OCFError, match="empty required narration"):
        service.migrate_bindings([record.id])


def test_binding_migration_surfaces_layer_validation_errors(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import yaml
    from ocf_tools import content
    from ocf_tools import eligibility as service
    from ocf_tools.utils import OCFError

    identity = "OCF-COG-001"
    path = tmp_path / "function.yaml"
    path.write_text(yaml.safe_dump({"function_id": identity}), encoding="utf-8")
    record = SimpleNamespace(
        id=identity,
        path=path,
        data={
            "narration": {"sequence": [{"key": "function.body"}]},
            "content": {
                "bindings": {
                    "session_templates": [],
                    "narration_resources": [],
                    "voice_sources": [],
                }
            },
        },
    )
    monkeypatch.setattr(service, "LocaleCatalog", lambda: object())
    monkeypatch.setattr(service, "load_function_by_id", lambda _: record)
    monkeypatch.setattr(content, "validate_layers", lambda *_: ["invalid binding shape"])

    with pytest.raises(OCFError, match="invalid binding shape"):
        service.migrate_bindings([identity])


def test_migration_report_counts_source_availability_without_promoting_release(
    monkeypatch,
):
    from types import SimpleNamespace

    from ocf_tools import eligibility as service

    monkeypatch.setattr(
        service,
        "load_all_functions",
        lambda: [SimpleNamespace(id="OCF-COG-001"), SimpleNamespace(id="OCF-COG-002")],
    )
    monkeypatch.setattr(
        service,
        "eligibility",
        lambda identity, locale: {
            "function_id": identity,
            "historical_source_availability": "available"
            if identity.endswith("1")
            else "unavailable",
            "tts_renderable": True,
            "release_ready": False,
        },
    )

    report = service.migration_report("es")

    assert report["locale"] == "es"
    assert report["total"] == report["tts_renderable"] == 2
    assert report["previous_source_available"] == 1
    assert report["previous_source_unavailable"] == 1
    assert all(not row["release_ready"] for row in report["functions"])


def test_binding_migration_is_idempotent_and_retains_old_sleep_template():
    from ocf_tools.indexes import load_function_by_id

    path = load_function_by_id("OCF-SLP-005").path
    before = path.read_bytes()
    rows = migrate_bindings(["OCF-SLP-005"], dry_run=True)
    assert rows[0]["dry_run"] is True
    assert path.read_bytes() == before
    from ocf_tools.content import load_layers

    binding = load_layers("OCF-SLP-005")["bindings"]
    assert binding["default_session_template"] == "OCF-TPL-SESSION-HPLUS-LOCKED-006"
    assert "OCF-TPL-SESSION-PILOT-SLEEP-EASY-001" in binding["session_templates"]
    assert binding["narration_plan"]["sequence"][1]["repetitions"] == 4
