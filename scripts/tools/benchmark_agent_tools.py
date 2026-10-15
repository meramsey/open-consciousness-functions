"""Measure local response-size proxies and wall time; never claim billed tokens."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools import agent_api as api  # noqa: E402
from ocf_tools import dev_jobs  # noqa: E402
from ocf_tools.indexes import load_function_by_id  # noqa: E402
from ocf_tools.paths import REPO_ROOT, work_path, workspace_run  # noqa: E402
from ocf_tools.utils import write_text_atomic  # noqa: E402


def measure(call):
    started = time.perf_counter()
    result = call()
    elapsed = time.perf_counter() - started
    text = (
        result
        if isinstance(result, str)
        else json.dumps(result, ensure_ascii=False, sort_keys=True)
    )
    return {
        "seconds": round(elapsed, 6),
        "utf8_bytes": len(text.encode("utf-8")),
        "characters": len(text),
        "estimated_tokens_chars_div_4": round(len(text) / 4, 1),
    }


def cli(*args):
    completed = workspace_run(
        [sys.executable, str(REPO_ROOT / "scripts/ocf.py"), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout


def main():
    record = load_function_by_id("OCF-FND-002")
    cases = {
        "function_lookup": (
            lambda: cli("functions", "describe", record.id, "--rich", "--json"),
            lambda: api.get_function(record.id),
        ),
        "single_function_validation": (
            lambda: cli("validate", str(record.path)),
            lambda: api.validate_function(record.id),
        ),
        "session_inspection": (
            lambda: cli("audio", "plan", record.id, "--expand"),
            lambda: api.get_session_plan(record.id),
        ),
        "audio_dry_run": (
            lambda: cli(
                "audio",
                "render",
                "OCF-SLP-005",
                "--voice",
                "OCF-VOICE-0002",
                "--pacing",
                "sleep",
                "--dry-run",
            ),
            lambda: api.plan_audio("OCF-SLP-005", "OCF-VOICE-0002"),
        ),
    }
    report = {
        "method": "UTF-8 bytes and characters/4 proxy; no provider billing/tokenizer data",
        "platform": sys.platform,
        "rows": {},
    }
    for name, (baseline, compact) in cases.items():
        report["rows"][name] = {
            "baseline": measure(baseline),
            "compact": measure(compact),
            "calls_each": 1,
        }
    request = {"paths": ["tests/test_loader_contracts.py"], "full": False, "workers": 1}
    baseline = measure(
        lambda: (
            workspace_run(
                [sys.executable, "-m", "pytest", *request["paths"], "-v"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            ).stdout
        )
    )
    started = time.perf_counter()
    job = dev_jobs.start("tests", request)
    start_latency = time.perf_counter() - started
    polls = 0
    while dev_jobs.status(job["job_id"])["state"] not in dev_jobs.TERMINAL:
        polls += 1
        time.sleep(0.2)
    total = time.perf_counter() - started
    report["rows"]["focused_pytest"] = {
        "baseline": baseline,
        "compact": measure(lambda: dev_jobs.job_result(job["job_id"])),
        "start_response_seconds": start_latency,
        "job_total_seconds": total,
        "poll_calls": polls,
        "counts": dev_jobs.job_result(job["job_id"])["data"],
    }
    report["rows"]["job_status_polling"] = {
        "baseline": measure(lambda: (dev_jobs.directory(job["job_id"]) / "state.json").read_text()),
        "compact": measure(lambda: dev_jobs.status(job["job_id"])),
        "calls_each": 1,
    }
    from ocf_tools.utils import _parsed_yaml, yaml_safe_load

    text = (REPO_ROOT / "locales/en-US/hplus-body-comfort.yaml").read_text(encoding="utf-8")
    _parsed_yaml.cache_clear()
    cold = measure(lambda: yaml_safe_load(text))
    warm = measure(lambda: [yaml_safe_load(text) for _ in range(100)])
    report["parser_cache"] = {
        "cold": cold,
        "warm_100": warm,
        "stats": _parsed_yaml.cache_info()._asdict(),
    }
    report["audio_operations"] = {
        "real_renders_started": 0,
        "avoided_by_dry_run": 2,
        "note": "Preflight does not synthesize; avoided operations are workflow choices, not observed billed savings.",
    }
    destination = work_path("logs", "agent-tool-benchmark.json")
    write_text_atomic(destination, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
