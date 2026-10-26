# Complete-session plans and bulk auditions

All 58 current OCF function records resolve complete English narration: 55
legacy-mapped records plus 3 OCF-original records. The historical 39/16
source-availability split applies only to legacy mappings. Script/resource review, technical
renderability, measured audio and release approval are different states.
`audio eligibility` derives them rather than persisting conflicting booleans.
Audio-rendered is unknown until a local output manifest is verified;
release-ready remains false for these planning/audition workflows.

## Author, bind and plan

1. Use `python3 scripts/ocf.py new function`; see
   [function lifecycle](FUNCTION_LIFECYCLE.md) and
   [source-first authoring](SOURCE_FIRST_AUTHORING.md).
2. Author/review locale narration under stable semantic keys. Preserve wording
   and command provenance; do not promote source availability or human review.
3. For the existing HPlus resource convention, preview
   `audio migrate-bindings FUNCTION_ID --dry-run`, then remove `--dry-run` to
   apply it deliberately. It fills missing sequences, upgrades only the known
   standard default, retains old templates, and preserves custom bindings.
   Other authoring styles use explicit `function-content/bindings/` records.
4. Run `validate --all`, `review commands`, and the narration integrity checker.
5. Generate plans with `audio plan`; the `new session-plan` wizard uses the same
   generator and validators.

```bash
python3 scripts/ocf.py audio eligibility OCF-FND-002 --locale en-US
python3 scripts/ocf.py audio plan OCF-FND-002 --locale en-US --dry-run
python3 scripts/ocf.py audio plan OCF-FND-002 --locale en-US
python3 scripts/ocf.py audio plan --all --locale en-US
python3 scripts/ocf.py audio plan --all --locale en-US --check
python3 scripts/ocf.py audio plan OCF-SLP-005 --locale en-US --expand
python3 scripts/ocf.py new session-plan
```

The predictable generated directory is `audio/session-plans/<locale>/`:
one compact declaration per function plus `_shared.json`. It records exact
function resource hashes, locale provenance, slot bindings, configuration
versions/hashes and a fingerprint of the composed semantic timing plan.
Timing remains relative to measured speech. There are no copied Sleep Easy
timestamps and no installed voice/codec/background engine requirement.
`--expand` is a read-only full pacing/DSP preview. `--check` fails on missing,
stale or unexpected generated files; writes refuse manually owned files.
Never hand-edit generated plans or indexes.

## Locked engineering defaults

`audio defaults` verifies the current immutable `OCF-AUDIO-DEFAULTS-HPLUS-014`
lock, version 14.0.0. The `...LOCKED-004` template/pacing successors preserve
their predecessors and select DSP successor `OCF-DSP-HPLUS-LOCKED-002`; the lock
fingerprints transitive runtime inputs. New revisions need a new baseline
identity; do not rewrite locked files in place.

Focus 10 starts immediately (OCF-BG-0012, approximate V4-derived candidate).
Focus 11 (OCF-BG-0006, canonical newer pure SAM) is selected only for access
and programming; entry is a 25-second equal-power transition and exit is a
10-second equal-power transition beginning at the measured close-instruction
onset. Focus 10 continues
through pauses, sleep, waking return and closer, with a 10-second ending fade.
There are two programming and two -24 dB sleep body passes, and no automatic
Focus 20 DSP. The shared preparation timeline includes a measured 20-second
breathing hold after “I will wait while you do this” and preserves the separate
20-second Transmutation Box hold after “Set it all aside for now.” Function-body blocks use measured
sentence units. No function wording was edited. Configuration locking does not
constitute human listening approval.

## Render explicitly

```bash
python3 scripts/ocf.py voice doctor
python3 scripts/ocf.py audio render-many OCF-FND-002 OCF-SLP-005 \
  --locale en-US --voice OCF-VOICE-0002 --workers 2 --dry-run
python3 scripts/ocf.py audio render-many OCF-FND-002 \
  --locale en-US --voice OCF-VOICE-0002 --workers 2 --resume
```

`--all` selects all eligible records but only when explicitly requested. It
does not run as part of planning or CI. `--dry-run` validates source plans
without requiring optional engines; run `voice doctor` and the existing
single-function `audio render --dry-run` for selected-engine preflight.
Full sessions default to at most two concurrent jobs; available RAM, CPU load
and free disk can reduce this, including to one worker. A process lock prevents
competing batches. Failure is reported per function and the batch continues;
interruption preserves per-function statuses and completed receipts.

Resume skips only matching configuration/voice/renderer inputs whose complete
manifest and every artifact still match checksums and sizes. Corrupt/missing
outputs produce a new unique audition. `--fresh-synthesis` bypasses every speech
cache while still skipping verified complete-session receipts; `--force` creates
a new audition even when one is already verified. Neither overwrites earlier
auditions. Speech-cache identity
includes exact text, locale, engine/model/configuration bytes, settings, rate,
package versions and renderer identity. Cache PCM is verified before reuse.
Auditions, receipts, cache and logs remain in `.ocf-work/`; nothing uploads audio.

Resume also verifies the effective background profile, preset/source bytes and
engine identity, including when no `--dsp-profile` override is supplied. Farfield
stem caching and bulk resume share one installed-runtime fingerprint: supported
Python console launchers bind the executable, interpreter, installed dependency
files and resolved implementation trees. Unknown/custom launchers or missing
identity disable verified resume and report that explicitly; they do not prevent
an otherwise supported render. The runtime must expose dependency metadata and
the optional `packaging` requirement parser for verified Farfield reuse; otherwise
reuse is bypassed. Active dependency markers/extras are respected, and unresolved
dependencies or bytecode-only imports cannot authorize reuse. No optional engine
is probed during dry-run.

Reference-master profiles bind the actual local source and splice files, profile
settings, without requiring Farfield. All backgrounds also bind the common
FFmpeg/FFprobe executables. Within one batch,
measured file hashes are reused only while resolved path, device/inode, size,
modification time and change time remain unchanged. Replacements are rehashed;
there is no persistent trust cache for private masters. This optimization assumes
ordinary local filesystem metadata, not hostile concurrent metadata manipulation.
`--force` bypasses both speech and DSP stem caches throughout nested render calls;
the normal cache policy is restored after the forced scope ends.

Inspect `session-report.json`, `session-timing-report.json`, the transcript and
the three `pacing-auditions/` excerpts. Listen and record human review separately.
For ordinary private FLAC/MP3 listening copies, run `audio export-audition
COMPLETED_SESSION_DIRECTORY --edition-version 0.1.0` with a deliberately selected
private edition. This defaults to configured OCF artwork with a visible edition
label. Existing compressed copies can be stream-copied with `--flac-source` and
`--mp3-source`; use `--no-artwork` only to disable the default explicitly. See
[private listening exports](AUDIO_PIPELINE.md#private-listening-exports-from-completed-sessions).
For a release, use the existing [release workflow](AUDIO_PIPELINE.md#final-release-packages)
with a registered implementation, explicit artwork and required rights/release
review. A generated plan is not an audio implementation or release clearance.

## Quality gates

```bash
python3 scripts/tools/check_hplus_narration_integrity.py
python3 scripts/ocf.py build-index --check
make check
make lint
python3 -m pytest
python3 -m pytest -n 2 --dist loadfile
```

Use focused tests while editing; the serial and two-worker commands both cover
the full suite. See [measured performance](releases/OCF_BULK_TEST_PERFORMANCE.md).
