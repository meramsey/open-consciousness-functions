"""Explicit small real Farfield/cache smoke; never a full function audition."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.audio_defaults import DSP_ID  # noqa: E402
from ocf_tools.paths import unique_run_id, work_path  # noqa: E402
from ocf_tools.semantic_dsp import load_profile, render_program  # noqa: E402
from ocf_tools.speech_cache import enabled  # noqa: E402
from ocf_tools.utils import write_text_atomic  # noqa: E402


def main():
    profile = load_profile(DSP_ID)
    profile["ignored_state_events"] = []
    profile["stage_backgrounds"] = {}
    document = {
        "schema_version": "1.0",
        "title": "Bounded DSP cache verification",
        "timeline": [
            {
                "id": "transition",
                "at": "00:05.000",
                "semantic": "focus.eleven.transition.open",
                "dsp": {"state": {"from": "focus-10", "to": "focus-11"}, "transition_s": 25},
            }
        ],
    }
    root = work_path("renders", unique_run_id("dsp-cache-review"))
    root.mkdir(parents=True)
    rows = []
    with enabled():
        for index in range(2):
            started = time.perf_counter()
            report = render_program(
                document,
                [{"id": "transition", "at": 5, "end": 30}],
                40,
                profile,
                root / f"sample-{index}.wav",
            )
            rows.append(
                {
                    "seconds": time.perf_counter() - started,
                    "output_sha256": report["output_sha256"],
                    "states": {
                        k: {
                            field: value.get(field)
                            for field in ("stem_cache", "stem_cache_stored", "stem_sha256")
                        }
                        for k, value in report["selections"].items()
                    },
                }
            )
    result = {
        "duration_seconds": 40,
        "runs": rows,
        "output_directory": str(root),
        "listening_approval": None,
    }
    write_text_atomic(root / "benchmark.json", json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
