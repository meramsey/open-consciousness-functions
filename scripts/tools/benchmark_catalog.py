"""Bounded public-data catalog microbenchmark; not a full-suite speed claim."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import platform
import statistics
import subprocess
import time
from dataclasses import asdict

from ocf_tools.locale import LocaleCatalog
from ocf_tools.paths import REPO_ROOT


def fingerprint(catalog):
    data = {
        tag: {
            "functions": pack.localized_functions,
            "entries": {key: asdict(value) for key, value in pack.entries.items()},
        }
        for tag, pack in catalog.packs.items()
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 20:
        parser.error("iterations must be between 1 and 20")
    rows, fingerprints = [], set()
    for _ in range(args.iterations):
        cpu, started = time.process_time(), time.perf_counter()
        catalog = LocaleCatalog()
        rows.append(
            {
                "wall_seconds": time.perf_counter() - started,
                "cpu_seconds": time.process_time() - cpu,
            }
        )
        if catalog.problems:
            raise RuntimeError(catalog.problems)
        fingerprints.add(fingerprint(catalog))
    profile = cProfile.Profile()
    profile.runcall(LocaleCatalog)
    scans = sum(
        entry.callcount
        for entry in profile.getstats()
        if getattr(entry.code, "co_name", None) == "resources"
        and entry.code.co_filename.endswith("function_catalog.py")
    )
    print(
        json.dumps(
            {
                "source_sha": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
                ).strip(),
                "dirty": bool(
                    subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT)
                ),
                "platform": platform.platform(),
                "python": platform.python_version(),
                "workers": 1,
                "workload": "complete LocaleCatalog construction; public repository data; no rendering",
                "runs": rows,
                "median_wall_seconds": statistics.median(row["wall_seconds"] for row in rows),
                "profiled_function_resource_scans": scans,
                "semantic_fingerprints": sorted(fingerprints),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
