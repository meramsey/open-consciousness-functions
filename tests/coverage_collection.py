"""Optional measurement harness: preserve audited taxonomy for per-test contexts."""

import json
import os
from pathlib import Path

import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    directory = os.environ.get("OCF_COVERAGE_COLLECTION")
    if not directory:
        return
    worker = getattr(session.config, "workerinput", {}).get("workerid", "serial")
    rows = [
        {
            "nodeid": item.nodeid,
            "unit": bool(item.get_closest_marker("unit")),
            "integration": bool(item.get_closest_marker("integration")),
        }
        for item in session.items
    ]
    (Path(directory) / f"collection-{worker}.json").write_text(
        json.dumps(rows, sort_keys=True), encoding="utf-8"
    )
