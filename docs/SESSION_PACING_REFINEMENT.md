# Complete-session pacing successor

The user explicitly authorized this engineering/editorial successor on 2026-10-27.
It is not human listening approval or publication authorization. Existing
HPLUS-014 files, narration resources and private v0.3.0 outputs remain immutable.

## Version chain and approved scope

| Component | Predecessor | Successor |
| --- | --- | --- |
| Audio defaults | HPLUS-014 | HPLUS-015 |
| Session template | HPLUS-LOCKED-004 | HPLUS-LOCKED-005 |
| Pacing | HPLUS-LOCKED-004 | HPLUS-LOCKED-005 |
| DSP | HPLUS-LOCKED-002 | HPLUS-LOCKED-003 |
| Sleep entry stage | FOCUS-TWENTY-ENTER-001 | FOCUS-TWENTY-ENTER-002 |
| Sleep exit stage | FOCUS-TWENTY-CLOSE-001 | FOCUS-TWENTY-CLOSE-002 |

Full IDs retain their existing `OCF-AUDIO-DEFAULTS-`, `OCF-TPL-SESSION-`,
`OCF-PACING-`, `OCF-DSP-` and `OCF-TPL-STAGE-HPLUS-` prefixes. The defaults
lock records resolved profile versions and SHA-256 hashes, including inherited
inputs. Historical locks retain their original profile projections.

The exact existing approved sentence “Relax and feel calm and serene in the
twentieth state.” moves from the pre-waking stage to immediately after the count
up to twenty. Its narration resource is reused, not rewritten or duplicated.
The approved repeated Twenty and waking wording remain unchanged. Twentieth
state is a narration convention, not a new Focus 20 DSP program.

## Measured timing policy

- Focus 11 exit remains a 10-second equal-power crossfade. Its end follows the
  measured audible endpoint of the unique sentence unit “The access signal, the
  access channel is closed.” within the semantic `focus.eleven.close` event.
  Missing, ambiguous, silent or invalid measurements fail; no Hearing timestamp
  or voice-specific duration is hardcoded. The existing 10 ms RMS speech-bound
  detector excludes backend padding without modifying or speeding up narration.
- Entry remains 25 seconds. DSP gain functions, bed gains, sidechain compression,
  finite-source checks and final fade are unchanged. Focus 10 remains continuous
  through sleep and waking. The source is never looped or substituted.
- Initial sleep rest: 60 seconds after the relocated sentence's measured end.
- Inter-pass rest: 60 seconds after the third complete function-body pass.
- Post-pass rest: 3 seconds before the existing waking instructions.
- Four complete passes remain: two normal, two at the existing -24 dB underlay.
- Breathing and Transmutation Box holds remain separate 20-second intervals.
  All other preparation, internal narration pacing and countdowns are preserved.

The 30–45-minute window and approximately 42-minute preference are advisory
metadata, configurable through a pacing profile. They never add arbitrary padding,
truncate narration, accelerate speech, or reject necessary longer sessions.
Optional preparation remains additive. Explicit function/profile overrides keep
precedence. Standard successor renders receive measured timing checks; explicitly
customized structures remain governed by their selected overrides.

## Private edition and recovery

The private edition inventory under `.ocf-work/agent-continuity/` is authoritative
for allocated local editions. A new edition must not reuse v0.3.0 output paths.
Public CI uses synthetic fixtures only. The 58-function duration audit records
old measured endpoints and proposed timings separately; fresh synthesis must be
remeasured before technical verification.

The existing detached supervisor accepts edition-specific configuration through
`OCF_REFERENCE_V4_VERSION`, `OCF_REFERENCE_V4_PROFILE` and optional
`OCF_REFERENCE_V4_FUNCTIONS` (space-separated pilot IDs). Nonhistorical versions
receive separate supervisor state/log files. Keep one owner per edition.
`OCF_REFERENCE_V4_PRUNE_VERIFIED_WAV=1` opts into the approved retention policy:
only receipt-owned WAV intermediates inside the render workspace are removed,
after checksummed export and QC. Historical v0.3.0 pruning is refused. Reports,
failed diagnostics, private sources and voice models are never deleted.

The batch exports each completed function promptly. Resume checks the selected
successor, edition profile, report and artifact hashes, and can recover verified
exports after intermediate cleanup. Combined packages and dashboards are built
from verified exports with relative links; audio remains private.
