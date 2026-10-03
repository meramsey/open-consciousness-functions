"""Reuse a frozen V1 speech/ledger for an RC1 DSP-only development audition.

Not a production mastering workflow. Inputs and outputs are explicit paths;
source speech, subtitles and session data are copied without regeneration.
``--label``/``--profile`` select the audition version and DSP profile; each
version keeps its own preserved directory so earlier auditions stay comparable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ocf_tools.semantic_dsp import _sha, load_profile, render_program  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="V2", help="audition version, e.g. V2 or V2.1")
    parser.add_argument("--profile", default="OCF-DSP-DEVELOPMENT-V4-001")
    args = parser.parse_args()
    manifest = yaml.safe_load((args.v1 / "render-manifest.yaml").read_text())
    for relative, expected in manifest["rc1_source_sha256"].items():
        if relative.startswith(("locales/", "audio/templates/")):
            if _sha(ROOT / relative) != expected:
                raise RuntimeError(f"RC1 source changed: {relative}")
    source = next(args.v1.glob("*-narration.wav"))
    if _sha(source) != manifest["artifacts"][source.name]["sha256"]:
        raise RuntimeError("V1 speech checksum mismatch")
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    args.output.mkdir(parents=True)
    prefix = f"DEVELOPMENT-AUDITION-{args.label}-OCF-Preparation-Learning-en-US-RC1"
    designation = f"DEVELOPMENT AUDITION {args.label} — NOT PRODUCTION MASTER"
    speech = args.output / f"{prefix}-narration.wav"
    shutil.copyfile(source, speech)
    for name in (
        "session-semantic.yaml",
        "session-resolved.en-US.yaml",
        "resolved-semantic-event-ledger.yaml",
        "narration-render-metadata.yaml",
        "timing-report.yaml",
        "utterance-timing.csv",
    ):
        shutil.copyfile(args.v1 / name, args.output / name)
    for suffix in ("srt", "lrc"):
        shutil.copyfile(next(args.v1.glob(f"*.{suffix}")), args.output / f"{prefix}.{suffix}")
    doc = yaml.safe_load((args.v1 / "session-semantic.yaml").read_text())
    with wave.open(str(speech)) as reader:
        duration = reader.getnframes() / reader.getframerate()
    bed = args.output / f"{prefix}-DSP-bed.wav"
    profile = load_profile(args.profile)
    program = render_program(doc, manifest["event_timing"], duration, profile, bed)
    (args.output / "semantic-dsp-render.yaml").write_text(yaml.safe_dump(program, sort_keys=False))
    commands = []

    def run(command):
        result = subprocess.run(command, text=True, capture_output=True, timeout=600)
        commands.append(command)
        with (args.output / "engine.log").open("a") as log:
            log.write(json.dumps(command) + "\n" + result.stdout + result.stderr + "\n")
        if result.returncode:
            raise RuntimeError(result.stderr[-2000:])

    master = args.output / f"{prefix}-master.wav"
    mix = "[0:a]aformat=channel_layouts=stereo[n];[1:a]volume=0.15[b];[n][b]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97:latency=1:level=0[out]"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(speech),
            "-i",
            str(bed),
            "-filter_complex",
            mix,
            "-map",
            "[out]",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s24le",
            "-metadata",
            f"comment={designation}",
            str(master),
        ]
    )
    for suffix, codec in [
        ("flac", ["-c:a", "flac", "-compression_level", "5"]),
        ("mp3", ["-c:a", "libmp3lame", "-b:a", "192k"]),
    ]:
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-i",
                str(master),
                *codec,
                str(args.output / f"{prefix}-listening.{suffix}"),
            ]
        )
    sources = [
        ROOT / "scripts/tools/render_development_v2.py",
        ROOT / "scripts/ocf_tools/semantic_dsp.py",
        ROOT / f"audio/background/state-profiles/{program['profile_id']}.yaml",
    ]
    sources += [
        ROOT / selection["preset_file"]
        for selection in program["selections"].values()
        if selection["mode"] == "preset"
    ]
    result = {
        "designation": designation,
        "audition_label": args.label,
        "dsp_profile": program["profile_id"],
        "git_base": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": {str(path.relative_to(ROOT)): _sha(path) for path in sources},
        "speech_reused_byte_for_byte": _sha(speech) == _sha(source),
        "v1_speech_sha256": _sha(source),
        "v1_render_manifest_sha256": _sha(args.v1 / "render-manifest.yaml"),
        "total_duration_s": duration,
        "event_timing": manifest["event_timing"],
        "narration_timing": manifest["narration_timing"],
        "DSP": program,
        "background_gain": 0.15,
        "mix_filter": mix,
        "external_commands": commands,
        "operational_cues_enabled": False,
        "artifacts": {
            path.name: {"sha256": _sha(path), "bytes": path.stat().st_size}
            for path in args.output.iterdir()
            if path.is_file() and path.name != "engine.log"
        },
    }
    (args.output / "render-manifest.yaml").write_text(yaml.safe_dump(result, sort_keys=False))
    print(f"Completed {args.label}: {duration:.6f}s -> {args.output}")


if __name__ == "__main__":
    main()
