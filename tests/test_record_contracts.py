"""Isolated authoring-to-record contracts; no repository schema/workflow execution."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools import prompts
from ocf_tools.models import function_from_dict

pytestmark = pytest.mark.unit


def fields(**extras):
    return {
        "function_id": "OCF-COG-999",
        "slug": "fixture",
        "name": "Mémoire",
        "primary_domain": "cognition",
        "canonical_command": "PLUS-THINK",
        "short_name": "Remember details",
        **extras,
    }


def test_community_record_defaults_identity_and_unknown_provenance(monkeypatch):
    monkeypatch.setattr(prompts, "current_date", lambda: "2026-10-03")
    data = prompts.build_function_yaml(**fields())
    record = function_from_dict(data, Path("fixture.yaml"))
    assert (record.id, record.slug, record.canonical_name) == ("OCF-COG-999", "fixture", "Mémoire")
    assert record.canonical_command == "PLUS-THINK"
    assert record.purpose_summary == "Remember details"
    assert record.maturity == "community-proposed"
    assert record.source_availability == "pending-source-review"
    assert record.reimplementation_status == "planned"
    assert record.evidence_state == "unverified"
    assert record.sources[0].type == "pending-source-review"
    assert record.sources[0].locator is None and record.sources[0].url is None
    assert record.sources[0].title == "pending-source-review"
    assert data["version"] == {"current": "0.1.0", "created": "2026-10-03", "updated": "2026-10-03"}
    assert data["attribution"]["original_authors"] == []


def test_legacy_record_mapping_modes_release_and_sources_remain_distinct(monkeypatch):
    monkeypatch.setattr(prompts, "current_date", lambda: "2026-10-03")
    data = prompts.build_function_yaml(
        **fields(
            notes="Human rationale",
            purpose="Intended operation",
            legacy_name="Source name",
            legacy_commands=["PLUS-THINK", "PLUS-OLD"],
            command_status="normalized",
            modes=["PLUS-MODE MORE", "PLUS-MODE LESS"],
            secondary_domains=["sleep", "invalid"],
            source_files=["source.txt"],
            source_urls=["https://example.invalid"],
            community_notes=["Unverified account"],
            rationale="Intentional mapping",
            compat_state="alias-listed",
            contributor_name="Editor",
            source_availability="available",
            reimplementation_status="draft",
            evidence="source-described",
            persistence="conditional",
            activation="manual",
            release_required=True,
            release_command="PLUS-END",
            safety_level="health",
            medical_relevance=True,
            safety_notes=["Review claim"],
            audio_status="review",
            background_status="required",
        )
    )
    record = function_from_dict(data, Path("fixture.yaml"))
    assert record.legacy_name == "Source name" and record.command_status == "normalized"
    assert record.command_review == "needs-review" and record.compatibility == "alias-listed"
    assert record.legacy_commands == ["PLUS-THINK", "PLUS-OLD"]
    assert data["aliases"]["commands"] == ["PLUS-OLD"]
    assert record.primary_domain == "cognition" and record.secondary_domains == ["sleep"]
    assert record.persistence == "conditional" and record.activation == "manual"
    assert record.release_required and record.release_command == "PLUS-END"
    assert record.purpose_summary == "Intended operation"
    assert record.safety_level == "health" and record.safety_notes == ["Review claim"]
    assert (
        record.audio_script_status == "review"
        and record.audio_implementation_status == "not-started"
    )
    assert record.background_strategy == "required" and record.background_preset is None
    assert [source.type for source in record.sources] == [
        "reference-file",
        "web",
        "community-notes",
    ]
    assert record.sources[1].url == "https://example.invalid"
    assert "Human rationale" in data["history"][0]["note"]
    # Accessor copies and Source objects cannot mutate canonical metadata.
    record.command_modes.append("PLUS-INVENTED")
    record.sources[0].title = "Changed accessor"
    assert record.command_modes == ["PLUS-MODE MORE", "PLUS-MODE LESS"]
    assert data["sources"][0]["title"] == "source.txt"
    assert record.to_dict() is data


@pytest.mark.parametrize(
    "status,expected",
    [("unchanged", "unchanged"), ("normalized", "alias-listed"), (None, "alias-listed")],
)
def test_missing_compatibility_fallback_and_spoken_command_counts(status, expected):
    record = function_from_dict(
        {
            "id": "OCF-COG-999",
            "slug": "fixture",
            "legacy": {"command_status": status},
            "canonical": {
                "command": {"primary": None, "modes": ["", "PLUS-SEE MORE", "PLUS-TWO, TWO"]}
            },
        },
        Path("fixture"),
    )
    assert record.compatibility == expected
    assert record.spoken_words() == [("PLUS-SEE MORE", 2), ("PLUS-TWO, TWO", 2)]
    assert record.release_required is False and record.release_command is None
    assert record.sources == []
    assert record.safety_level == "general"


@pytest.mark.parametrize("data", [{}, {"id": "OCF-COG-999"}, {"slug": "fixture"}])
def test_missing_identity_rejected_before_record_use(data):
    with pytest.raises(ValueError, match="missing 'id' or 'slug'"):
        function_from_dict(data, Path("fixture"))


def test_next_ids_use_canonical_records_and_named_proposal_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(prompts, "load_all_functions", lambda: [])
    assert prompts.next_function_id("cognition") == "OCF-COG-001"
    monkeypatch.setattr(
        prompts,
        "load_all_functions",
        lambda: [SimpleNamespace(id="OCF-COG-009"), SimpleNamespace(id="OCF-FND-999")],
    )
    assert prompts.next_function_id("cognition") == "OCF-COG-010"
    monkeypatch.setattr(prompts, "REPO_ROOT", tmp_path)
    assert prompts.next_proposal_id() == "OCFP-0001"
    proposals = tmp_path / "proposals/draft"
    proposals.mkdir(parents=True)
    for name in ("ocfp-0002.md", "ocfp-0009-semantic-narration.md", "ocfp-invalid.md", "other.md"):
        (proposals / name).write_text("fixture")
    assert prompts.next_proposal_id() == "OCFP-0010"
    manifests = tmp_path / "audio/manifests"
    monkeypatch.setattr(prompts, "AUDIO_MANIFESTS_DIR", manifests)
    assert prompts.next_audio_id() == "OCF-AUDIO-0001"
    assert prompts.next_background_id() == "OCF-BG-0001"
    manifests.mkdir(parents=True)
    (manifests / "OCF-AUDIO-0009.yaml").write_text("id: OCF-AUDIO-0009")
    (manifests / "README.yaml").write_text("title: fixture")
    assert prompts.next_audio_id() == "OCF-AUDIO-0010"
    backgrounds = tmp_path / "audio/background/manifests"
    backgrounds.mkdir(parents=True)
    (backgrounds / "OCF-BG-0012.yaml").write_text("id: OCF-BG-0012")
    (backgrounds / "README.yaml").write_text("title: fixture")
    assert prompts.next_background_id() == "OCF-BG-0013"


def test_background_builder_retains_unknowns_and_explicit_zero_seed():
    common = dict(
        bg_id="OCF-BG-9999",
        name="Fixture",
        author="",
        engine="farfield",
        preset_file="",
        provenance="unknown",
        notes="",
        intended="",
        functions=[],
        seed="0",
        fmt="wav",
        render_notes="",
        headphone=True,
        driving=True,
        safety_notes=[],
        license_="unknown",
    )
    data = prompts.background_manifest_yaml(**common)
    assert data["author"] == "pending-source-review"
    assert data["preset"]["file"] is None and data["provenance"]["notes"] is None
    assert data["render"]["seed"] == 0
    assert data["license"] == "unknown"
    other = prompts.background_manifest_yaml(**{**common, "engine": "sbagenx", "seed": "unknown"})
    assert other["engine_source"]["repository"] is None and other["render"]["seed"] is None


def test_write_confirmation_and_atomic_collision_error(monkeypatch, tmp_path, capsys):
    path = tmp_path / "record.yaml"
    assert prompts._confirm_write(path)
    path.write_text("old")
    monkeypatch.setattr(prompts, "ask_yes_no", lambda *a, **kw: prompts.PromptResult("no", "value"))
    assert not prompts._confirm_write(path)
    monkeypatch.setattr(
        prompts, "ask_yes_no", lambda *a, **kw: prompts.PromptResult("yes", "value")
    )
    assert prompts._confirm_write(path)
    assert prompts._atomic_write_or_warn(path, "new") and path.read_text() == "new"

    def collision(*args, **kwargs):
        raise prompts.OCFFileExistsError("collision")

    monkeypatch.setattr(prompts, "write_text_atomic", collision)
    assert not prompts._atomic_write_or_warn(path, "not written")
    assert path.read_text() == "new" and "collision" in capsys.readouterr().out
