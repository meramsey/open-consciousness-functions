"""Shared pytest configuration: make the OCF tooling importable."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def sample_function_path() -> Path:
    return Path(__file__).parent / "fixtures" / "function-sample.yaml"


@pytest.fixture()
def sample_background_path() -> Path:
    return Path(__file__).parent / "fixtures" / "background-sample.yaml"


# Conservative audited classifications, not speed-based guesses. Remaining
# repository/workflow tests stay integration until individually audited.
UNIT_MODULES = {
    "test_locale",
    "test_locale_correctness",
    "test_localized_timing",
    "test_audio_build",
    "test_recordings",
    "test_semantic_dsp",
    "test_preservation",
    "test_corpus_relations",
    "test_content",
    "test_planning",
    "test_diagnostics",
    "test_packaged_data",
    "test_bootstrap",
    "test_container_config",
    "test_recording_import",
    "test_disabled_narration",
    "test_voice_registry",
    "test_boundary_coverage",
    "test_extraction_completion",
}
REAL_AUDIO_TESTS = {
    "test_actual_ffmpeg_envelopes_and_seeded_output",
    "test_actual_ffmpeg_approach_envelope_matches_planned_gain",
    "test_actual_pcm24_conversion_preserves_duration_and_original",
}


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("unit") or item.get_closest_marker("integration"):
            continue
        if item.originalname in REAL_AUDIO_TESTS:
            item.add_marker(pytest.mark.audio_integration)
            item.add_marker(pytest.mark.external_tool)
            item.add_marker(pytest.mark.integration)
        elif item.path.stem in UNIT_MODULES:
            item.add_marker(pytest.mark.unit)
        else:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def unit_process_boundary(request, monkeypatch):
    if request.node.get_closest_marker("unit"):
        import subprocess

        def forbidden(*args, **kwargs):
            pytest.fail(
                "unit tests must stub external process execution; classify real engines as integration"
            )

        monkeypatch.setattr(subprocess, "Popen", forbidden)
