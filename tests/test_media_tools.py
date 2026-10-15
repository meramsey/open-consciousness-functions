import time

import pytest
from ocf_tools import agent_api as api
from ocf_tools import dev_jobs


def test_media_discovery_and_unsupported_training_are_truthful(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    assert {
        "ocf_generate_artwork_preview",
        "ocf_start_voice_audition",
        "ocf_plan_voice_training",
    } <= api.TOOLS.keys()
    assert "ocf_inspect_brand" in api.READ_ONLY
    assert "ocf_generate_artwork_preview" not in api.READ_ONLY
    assert api.inspect_brand()["human_approval"] is None
    assert api.list_artwork_themes()["surfaces"] == {
        "ui": "ocf-light",
        "artwork": "ocf-dark",
        "documentation": "ocf-minimal",
    }
    assert api.validate_theme("../outside.json")["status"] == "failed"
    assert api.plan_voice_training()["training_supported"] is False
    assert any(p["id"] == "OCF-VOICE-0002" for p in api.list_voice_profiles()["items"])


def test_artwork_uses_existing_persistent_job_queue(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    job = api.generate_artwork_preview("OCF-SLP-005", resolution=256)
    assert "job_id" in job, job
    deadline = time.monotonic() + 60
    while (
        api.get_job_status(job["job_id"])["state"] not in dev_jobs.TERMINAL
        and time.monotonic() < deadline
    ):
        time.sleep(0.1)
    result = api.get_job_result(job["job_id"])
    if result["state"] not in dev_jobs.TERMINAL:
        api.cancel_job(job["job_id"])
    assert result["state"] == "completed", result
    assert result["data"]["review_status"] == "candidate"
    assert result["data"]["human_approval"] is None
