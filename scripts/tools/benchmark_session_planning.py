"""Public complete-session planning benchmark; does not measure audio rendering."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time

from ocf_tools.indexes import load_all_functions
from ocf_tools.paths import REPO_ROOT
from ocf_tools.session_plans import serialize, source_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", help="all 58 planning identities; no synthesis"
    )
    parser.add_argument("--function", default="OCF-FND-002")
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 10:
        parser.error("iterations must be between 1 and 10")
    ids = sorted(row.id for row in load_all_functions()) if args.all else [args.function]
    runs, hashes = [], set()
    for _ in range(args.iterations):
        started, cpu = time.perf_counter(), time.process_time()
        outputs = {}
        for identity in ids:
            plan, shared, expanded = source_plan(identity)
            outputs[identity] = hashlib.sha256(
                serialize(
                    {
                        "plan": plan,
                        "shared": shared,
                        "expanded": expanded,
                    }
                ).encode()
            ).hexdigest()
        wall = time.perf_counter() - started
        runs.append(
            {
                "wall_seconds": wall,
                "cpu_seconds": time.process_time() - cpu,
                "planned_sessions_per_hour": 3600 * len(ids) / wall,
            }
        )
        hashes.add(hashlib.sha256(serialize(outputs).encode()).hexdigest())
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
                "workload": "public canonical complete-session planning; no synthesis, DSP rendering, mixing or packaging",
                "function_ids": ids,
                "runs": runs,
                "median_wall_seconds": statistics.median(row["wall_seconds"] for row in runs),
                "output_fingerprints": sorted(hashes),
                "last_plan_output_hashes": outputs,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
