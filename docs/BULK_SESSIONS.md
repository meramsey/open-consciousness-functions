# Complete-session plans and bulk auditions

All 55 current functions resolve complete English narration. The historical
39/16 source-availability split is unchanged. Script/resource review, technical
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

`audio defaults` verifies `OCF-AUDIO-DEFAULTS-HPLUS-001`, version 1.0.0.
The new LOCKED template and pacing profiles inherit the retained STANDARD
drafts; the lock fingerprints their transitive runtime inputs. New revisions
need a new baseline identity; do not rewrite the locked files in place.

Focus 10 starts immediately (OCF-BG-0012, approximate V4-derived candidate).
Focus 11 (OCF-BG-0006, canonical newer pure SAM) is selected only for access
and programming, with 25-second equal-power transitions. Focus 10 continues
through pauses, sleep, waking return and closer, with a 10-second ending fade.
There are two programming and two -24 dB sleep body passes, and no automatic
Focus 20 DSP. Semantic pacing retains relaxation and count defaults; body
comfort/transmutation-box preparation gains 3-second instruction pauses at
rate scale 1.0. No approved wording was edited. Configuration locking does not
constitute human listening approval.

## Render explicitly

```bash
python3 scripts/ocf.py voice doctor
python3 scripts/ocf.py audio render-many OCF-FND-002 OCF-SLP-005 \
  --locale en-US --voice OCF-VOICE-0002 --dry-run
python3 scripts/ocf.py audio render-many OCF-FND-002 \
  --locale en-US --voice OCF-VOICE-0002 --resume
```

`--all` selects all eligible records but only when explicitly requested. It
does not run as part of planning or CI. `--dry-run` validates source plans
without requiring optional engines; run `voice doctor` and the existing
single-function `audio render --dry-run` for selected-engine preflight.
Full sessions run serially (one memory-bounded worker). Failure is reported
per function and the batch continues; interruption preserves completed receipts.

Resume skips only matching configuration/voice/renderer inputs whose complete
manifest and every artifact still match checksums and sizes. Corrupt/missing
outputs produce a new unique audition. `--force` regenerates audio and bypasses
speech-cache reuse; it never overwrites earlier auditions. Speech-cache identity
includes exact text, locale, engine/model/configuration bytes, settings, rate,
package versions and renderer identity. Cache PCM is verified before reuse.
Auditions, receipts, cache and logs remain in `.ocf-work/`; nothing uploads audio.

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
