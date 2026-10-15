import json

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
    assert current == unavailable


def test_spoken_locale_missing_dependency_is_reported_without_cross_language_fallback():
    result = eligibility("OCF-FND-002", "es")
    assert not result["tts_renderable"]
    assert result["blockers"]
    assert not result["release_ready"]


def test_binding_migration_is_idempotent_and_retains_old_sleep_template():
    path = REPO_ROOT / "function-content/bindings/OCF-SLP-005.yaml"
    before = path.read_bytes()
    rows = migrate_bindings(["OCF-SLP-005"], dry_run=True)
    assert rows[0]["dry_run"] is True
    assert path.read_bytes() == before
    from ocf_tools.content import load_layers

    binding = load_layers("OCF-SLP-005")["bindings"]
    assert "OCF-TPL-SESSION-HPLUS-STANDARD-001" in binding["session_templates"]
    assert binding["narration_plan"]["sequence"][1]["repetitions"] == 4
