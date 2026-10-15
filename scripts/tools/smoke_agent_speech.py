"""Explicit optional real Piper/cache smoke; short approved resource, no full session."""

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.locale import LocaleCatalog  # noqa: E402
from ocf_tools.narration_first import _voice_profile  # noqa: E402
from ocf_tools.paths import unique_run_id, work_path  # noqa: E402
from ocf_tools.speech_cache import STATS, enabled  # noqa: E402
from ocf_tools.voice import _read_pcm_from_bytes, render_cue_wav  # noqa: E402


def main():
    catalog = LocaleCatalog()
    _, spec = _voice_profile("OCF-VOICE-0002", "en-US", catalog)
    resource, _ = catalog.resource(
        "hplus.shared.focus11.open", "en-US", domain="narration", fallback=False
    )
    elapsed = []
    data = []
    with enabled():
        for _ in range(2):
            started = time.perf_counter()
            data.append(render_cue_wav(spec, resource.text))
            elapsed.append(time.perf_counter() - started)
    assert data[0] == data[1]
    rate, samples = _read_pcm_from_bytes(data[0])
    path = work_path("renders", unique_run_id("speech-cache-smoke") + ".wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data[0])
    print(
        json.dumps(
            {
                "seconds": elapsed,
                "cache_counters": STATS,
                "sample_rate": rate,
                "duration_seconds": len(samples) / rate,
                "sha256": hashlib.sha256(data[0]).hexdigest(),
                "output": str(path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
