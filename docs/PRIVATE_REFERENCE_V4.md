# Private reference-V4 listening editions

The registry currently contains 58 OCF function records: 55 legacy-mapped
functions and 3 OCF-original functions. Historical source availability, plan
validity, technical render verification, human listening approval and
publication authorization are separate statuses.

## Current shared-session successor

The immutable HPLUS-014 lock selects the `...LOCKED-004` session and pacing
successors, plus the `...LOCKED-002` DSP successor. Function-body blocks are
now synthesized and timed as measured sentence units, with the configured
0.4-second internal sentence spacing and no invented transcript alignment.
The shared standard session successor adds a 20-second semantic breathing hold
anchored to the measured end of “I will wait while you do this.” The existing
20-second Transmutation Box interval begins after the measured end of “Set it
all aside for now”; it remains a separate hold. No silence is added after other
preparation phrases. The standard Focus 11-to-10 equal-power
crossfade is 10 seconds and begins at the measured onset of “You will close
your plus access channel now as I guide you.” Entry remains 25 seconds; the
ending fade remains 10 seconds. Explicit per-function overrides remain in force.

The pre-waking instruction has its own versioned narration key: “Relax and feel
calm and serene in the twentieth state.” Focus 10 remains the selected DSP
background during sleep and waking; no Focus 20 DSP profile is introduced. The
function body remains two normal Focus 11 programming passes plus two -24 dB
sleep-reinforcement passes.

## Local private render and recovery

Reference V4 source files, Amy Medium model/configuration, profiles, render
masters, logs and packages are operator-local. Keep them under the dedicated
`.ocf-work/` workspace and never stage or publish them. Only the per-function
package outputs explicitly verified by the exporter belong in the private
edition collection. The original source files and prior editions are inputs,
not output destinations.

Use the configured Python 3.11+ environment, local Piper `en_US-amy-medium`,
and selected `OCF-VOICE-9003` profile. After Hearing passes technical gates,
continue the private collection with the batch driver:

```bash
OCF_WORK_DIR="$PWD/.ocf-work" \
  .venv/bin/python scripts/tools/render_private_reference_v4.py --all \
  --profile "$OCF_REFERENCE_V4_PROFILE" --voice OCF-VOICE-9003 \
  --version 0.3.0 --workers 2 --fresh-synthesis
```

The scheduler reduces concurrency based on available memory, disk and CPU load.
Each function status is persisted; individual failures do not block others.
Fresh synthesis bypasses speech caches from prior editions while checksummed
whole-session receipts support safe resume. Exports, measured lyrics, provenance,
quality evidence, guides, package and relative-path indexes are built privately.
Set `OCF_REFERENCE_V4_PROFILE` to the local YAML containing the configured
Focus 10/11 preset locations; never commit that machine-specific file.
Never overwrite historical editions. A batch lock prevents competing render
owners; inspect the recorded PID before removing an unreadable/stale lock.

The reference-V4 edition is private-only. MP3 and FLAC exports carry measured
plain and synchronized lyrics where supported, with portable TXT/LRC/SRT/VTT
and timing sidecars. Technical verification does not imply human listening
approval; listening approval does not authorize publication. Android player
compatibility is not claimed without device/player verification.

Run the portable index builder only after the collection package passes its
checksummed verification:

```bash
PYTHONPATH=scripts python scripts/tools/build_private_collection_index.py \
  .ocf-work/renders/amy-reference-v4-v0.3.0/package \
  .ocf-work/renders/amy-reference-v4-v0.3.0/indexes \
  --progress .ocf-work/agent-continuity/REFERENCE_V4_V0_3_0_STATUS.json
```

The resulting HTML, Markdown, dashboard JSON and relative-path M3U list only
verified package tracks. Failed, blocked and pending functions remain visible
in the dashboard but are not added to the playlist.

For Android transfer, copy the complete edition directory so `indexes/playlist.m3u`
stays beside its `package/` directory; the playlist uses relative paths. Inspect
tags with `python scripts/ocf.py audio inspect <file.mp3>` or `ffprobe`, and open
the same-basename `.lrc` when a player does not show embedded synchronized
lyrics. The exporter reads back MP3 ID3 and FLAC lyric tags, but Poweramp/Plexamp
UI compatibility remains unverified until checked on an actual device.
