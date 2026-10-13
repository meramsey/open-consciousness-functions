"""Derived-data serialization with injected records; real repository indexes are untouched."""

import csv
import io
import json

import pytest
from ocf_tools import content
from ocf_tools import generators as g
from ocf_tools.models import function_from_dict
from ocf_tools.paths import GENERATED_HEADER

pytestmark = pytest.mark.unit


@pytest.fixture
def records(monkeypatch, tmp_path):
    def make(index, availability, status, name, primary):
        return function_from_dict(
            {
                "id": f"OCF-FND-{index:03}",
                "slug": f"fixture-{index}",
                "canonical": {
                    "name": name,
                    "command": {
                        "primary": primary,
                        "modes": ["PLUS-EXAMPLE MORE", "PLUS-EXAMPLE LESS"],
                    },
                },
                "legacy": {
                    "name": f"Source {index}",
                    "commands": ["PLUS-OLD, COMMAND"],
                    "command_status": status,
                    "source_availability": availability,
                },
                "classification": {
                    "primary_domain": "foundation",
                    "secondary_domains": ["cognition"],
                },
                "ocf": {"reimplementation_status": "planned", "command_review": "needs-review"},
                "compatibility": {"state": "alias-listed"},
                "lifecycle": {"persistence": "temporary"},
                "status": {"maturity": "legacy-mapped"},
                "safety": {
                    "level": "general",
                    "medical_relevance": index == 2,
                    "notes": ["Human review"],
                },
            },
            tmp_path / f"functions/fixture-{index}.yaml",
        )

    rows = [
        make(1, "available", "unchanged", "Café | Example", "PLUS-FOCUS"),
        make(2, "unavailable", "normalized", "Second", None),
        make(3, "available", "proposed", "Third", "PLUS-THIRD"),
    ]
    monkeypatch.setattr(g, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(g, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(g, "LEGACY_DIR", tmp_path / "legacy")
    monkeypatch.setattr(g, "load_all_functions", lambda: rows)
    monkeypatch.setattr(g, "generated_command_documents", lambda: [])
    monkeypatch.setattr(g, "audio_implementations_for", lambda id: [{}] if id == rows[0].id else [])
    monkeypatch.setattr(
        g, "background_presets_for", lambda id: [{}, {}] if id == rows[0].id else []
    )
    monkeypatch.setattr(
        content, "discover", lambda record: {"function_id": record.id, "human_review": "required"}
    )
    monkeypatch.setattr(
        content,
        "load_layers",
        lambda id: (
            {
                "specifications": {
                    "extraction_status": "complete",
                    "analysis_review": {
                        "source_extent": {"source_sha256": "a" * 64},
                        "claim_categories": ["unverified-claim"],
                        "sections": {"main": {"status": "supported"}},
                    },
                },
                "evidence": {
                    "sources": [{"sha256": "a" * 64, "evidence_class": "source_transcript"}]
                },
            }
            if id == rows[0].id
            else {}
        ),
    )
    monkeypatch.setattr(
        g,
        "load_audio_manifests",
        lambda: [
            {
                "id": "OCF-AUDIO-0001",
                "function_id": rows[0].id,
                "title": "Café | Audio",
                "language": "fr",
            }
        ],
    )
    monkeypatch.setattr(
        g,
        "load_background_manifests",
        lambda: [
            {
                "id": "OCF-BG-0001",
                "name": "Zero seed",
                "engine": "farfield",
                "render": {"seed": 0, "deterministic": True},
                "usage": {"functions": [rows[0].id]},
            },
            {"id": "OCF-BG-0002", "name": "Unknown seed"},
        ],
    )
    return rows, tmp_path


def body(text):
    assert text.startswith(GENERATED_HEADER + "\n\n")
    return text.split("\n\n", 1)[1]


def test_index_csv_json_and_legacy_maps_preserve_identity_and_unicode(records):
    rows, root = records
    row = g.row_for(rows[0])
    assert row["domains"] == "foundation;cognition"
    assert row["audio_impl_count"] == 1 and row["background_preset_count"] == 2
    assert row["source_file"] == "functions/fixture-1.yaml"
    csv_rows = list(csv.DictReader(io.StringIO(body(g.function_index_csv()))))
    assert csv_rows[0]["canonical_name"] == "Café | Example"
    assert csv_rows[0]["legacy_command"] == "PLUS-OLD, COMMAND"
    data = json.loads(body(g.function_index_json()))
    assert data["count"] == 3 and data["functions"][0]["capabilities"]["human_review"] == "required"
    legacy = json.loads(body(g.hplus_command_map_json()))
    assert legacy["mappings"][0]["legacy_commands"] == ["PLUS-OLD, COMMAND"]
    assert legacy["mappings"][0]["canonical_commands"][0] == "PLUS-FOCUS"
    assert (
        list(csv.DictReader(io.StringIO(body(g.hplus_command_map_csv()))))[1]["source_availability"]
        == "unavailable"
    )
    assert "Café \\| Example" in g.function_index_markdown()
    assert "3 functions listed" in g.function_index_markdown()


def test_review_matrices_do_not_promote_unknown_evidence(records):
    rows, _ = records
    commands = g.command_review_markdown()
    assert "1 commands are unchanged" in commands and "1 commands normalized" in commands
    assert "1 commands requiring review" in commands
    availability = g.availability_matrix_markdown()
    assert "Available: 2" in availability and "Source unavailable: 1" in availability
    roadmap = g.reimplementation_roadmap_markdown()
    assert "proposal pathway" in roadmap and "3 functions currently marked" in roadmap
    assert "| yes | Human review |" in g.safety_matrix_markdown()
    review = g.extraction_review_markdown()
    assert "source_transcript" in review and "supported" in review
    assert "unknown" in review and "HUMAN CONTENT REVIEW REQUIRED" in review
    assert "1 audio implementations recorded" in g.audio_implementation_index_markdown()
    background = g.background_audio_index_markdown()
    assert "| 0 | yes |" in background
    assert "|  | no |" in background


def test_generation_and_freshness_contracts_are_deterministic_and_detect_drift(records):
    _, root = records
    first = g.generate_all_content()
    assert first == g.generate_all_content()
    assert len(first) == 12 and len({path for path, _ in first}) == 12
    assert not g.indexes_are_fresh()
    paths = g.build_all_generated_files()
    assert len(paths) == 12 and all(path.is_relative_to(root) for path in paths)
    assert g.indexes_are_fresh()
    paths[0].write_text("changed metadata")
    assert not g.indexes_are_fresh()
    g.refresh_indexes()
    assert g.indexes_are_fresh()
