"""Silence is valid only when the semantic document genuinely has no speech."""

import pytest
from ocf_tools.utils import OCFError
from ocf_tools.voice import render_narration


def test_explicit_disabled_source_keeps_semantic_clock(tmp_path):
    doc = {
        "timeline": [
            {"id": "start", "at": 0, "semantic": "practice.begin"},
            {"id": "end", "at": 2, "semantic": "practice.complete"},
        ]
    }
    meta = render_narration(doc, tmp_path / "silent.wav", backend="disabled", sample_rate=8000)
    assert meta["backend"] == "disabled" and meta["cues"] == 0 and meta["duration"] == 3
    with pytest.raises(OCFError, match="cannot be silently dropped"):
        render_narration(
            {"timeline": [{"id": "speech", "at": 0, "text": "Required words."}]},
            tmp_path / "wrong.wav",
            backend="disabled",
        )
