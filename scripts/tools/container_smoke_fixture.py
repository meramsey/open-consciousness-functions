"""Create original synthetic recording fixtures for an explicit container smoke run."""

import argparse
import hashlib
import json
import wave
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    wav = args.directory / "test.wav"
    with wave.open(str(wav), "wb") as writer:
        writer.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        writer.writeframes(b"\x01\x00" * 800)
    session = {
        "schema_version": "1.0",
        "id": "synthetic-container-smoke",
        "title": "Synthetic container fixture",
        "locale": "en-US",
        "source": {"format": "manual"},
        "timeline": [{"id": "test", "at": 0, "text": "Synthetic test fixture."}],
    }
    package = {
        "schema_version": "1.0",
        "id": "synthetic-smoke",
        "source_type": "externally-generated",
        "locale": "en-US",
        "author": "OCF test fixture",
        "license": "Apache-2.0",
        "redistribution_permission": False,
        "recordings": {
            "test": {"file": "test.wav", "sha256": hashlib.sha256(wav.read_bytes()).hexdigest()}
        },
    }
    (args.directory / "session.yaml").write_text(yaml.safe_dump(session), encoding="utf-8")
    (args.directory / "package.yaml").write_text(yaml.safe_dump(package), encoding="utf-8")
    print(
        json.dumps(
            {"source_sha256": package["recordings"]["test"]["sha256"], "source_duration_s": 0.1}
        )
    )


if __name__ == "__main__":
    main()
