"""Optional measurement harness: preserve audited taxonomy for per-test contexts."""

import json
import os
from pathlib import Path

import pytest


def pytest_deselected(items):
    directory = os.environ.get("OCF_COVERAGE_COLLECTION")
    if not directory or not items:
        return
    worker = getattr(items[0].config, "workerinput", {}).get("workerid", "serial")
    path = Path(directory) / f"deselected-{worker}.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    path.write_text(json.dumps([*previous, *(item.nodeid for item in items)]), encoding="utf-8")


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
