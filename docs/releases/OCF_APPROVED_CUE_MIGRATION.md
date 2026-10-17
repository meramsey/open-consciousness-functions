# Approved English title–cue migration

The explicit user decisions in `OCF-EDITORIAL-TITLE-CUES-001` are implemented.
The predecessor is commit `21e63ac6f8bf5a7bce9506f033330df967aa4f97`.
This checkpoint does not approve listening, efficacy, historical authentication,
translations, branding or public release.

## Authoritative records and current presentation

- [Exact approval, previous/current values and per-entry diffs](../../function-content/editorial/approved-title-cues-001.json).
- [Current complete decision sheet](OCF_TITLE_CUE_CURRENT.md) and
  [machine-readable current catalog](OCF_TITLE_CUE_CURRENT.json).
- [Current teaching status](OCF_TEACHING_CURRENT.md),
  [source-English terminology](OCF_EN_US_TERMINOLOGY.md) and
  [historical lookup](OCF_HISTORICAL_LOOKUP_CURRENT.md).

Nine selected title/cue pairs, the user-selected Detox correction, and the heart
cue are applied. The heart retains **Heart: Repairs & Maintenance** and teaches
**Plus Heart Better**, with exact display **PLUS-HEART-BETTER**. Heart Flow is
the preferred tentative title, not an active title. Heart Renewal, Body Cleansing,
Body Cleanse and their rejected cue directions are not active defaults.
Nutricia, De-Hab alternatives, other unselected pairs and HPLUS identifier
migration remain pending.

## Integrity and engineering preservation

The protected scope remains 177 entries: 21 allowlisted values changed and 156
remain identical. Only exact approved cue/title substitutions and the necessary
Insulate self-reference grammar are permitted by the replay verifier. Every
changed entry retains its stable key and has an old/new hash and unified diff.
Entry versions advance; original source/provenance quotations remain historical.

The previous narration fixture and `OCF-AUDIO-DEFAULTS-HPLUS-001.json` remain
unchanged. Successor fixture `hplus-narration-text-baseline-002.json` and defaults
`OCF-AUDIO-DEFAULTS-HPLUS-002` select the new content. Both locks have the same
104 dependency names and identical profile identities; all 93 non-editorial
dependency hashes remain unchanged. Presets, DSP, transitions, underlay levels,
pacing and four-pass structure were not edited. The old lock and narration check
were also verified positively in their matching predecessor checkout.

All 55 compact plans are regenerated: the shared content-lock reference changes
for every plan, while affected resources carry their own new version/text hashes.
Timing remains measured-speech-relative; no old render timestamps are copied.

## History and localization

There are 55 functions, 55 stable primary command identities and 97 total
structured identities before and after. Seven superseded primary-alias records
are explicitly historical-only, leaving 90 active records. No secondary operation
was demoted. All 65 original legacy phrase mappings are retained. The new lookup
ledger records 33 predecessor field values; these are versioned lookup entries,
not 33 newly active aliases or necessarily distinct replacement phrases.

Spoken cue bindings are optional, explicit narration-resource keys, separate from
role labels and exact display spellings. Existing locale services resolve them;
missing/unreviewed localized speech is not silently borrowed for a complete
localized narration plan. Spanish remains partial and requires terminology review.
No production translations were changed. Per-locale Plus treatment remains a
future reviewed choice.

Old selected recordings with changed text fingerprints fail in recorded-only and
hybrid modes, even when a hybrid TTS fallback is otherwise allowed. Original
recordings/manifests and historical audio are not relabeled or overwritten.
Changed speech has a new synthesis identity; unchanged body/shared speech remains
reusable under the existing cache contract. Breathe Better's existing body cue
already matched, so that body text did not change.

## Actual bounded audio verification

Eleven Piper cue-in-context excerpts were generated from the actual activation
instructions using existing voice `OCF-VOICE-0002`; identical warm requests reused
cached PCM. They are local at:
`.ocf-work/renders/approved-title-cue-excerpts-20261017T005738-c8ec80e4/`.

One complete Sleep Easy audition was rendered through the existing queued service:
job `f198f1a8679c45f5878eb4859c5efe54`. Its local directory is:
`.ocf-work/renders/auditions/OCF-SLP-005-en-US-OCF-VOICE-0002-complete-session/OCF-SLP-005-20261017T005702-6fbd6543/`.

The session is 2300.280181 seconds, stereo 44.1 kHz, with four body passes, nine
updated cue mentions in its resolved transcript and no old Quiet Sleep cue.
Full master/background decode, artifact checksums, 14 active-background checks
and 15 representative stereo points passed; the master reports zero clipped
samples. Shared speech cache hits were 36, with 149 misses. Master SHA-256:
`1ff4813a279462739149403cfe040470b8733dca8b69ce41a3f1084ab07ab4ce`.

The narration input/transcript and resource-version checks are not ASR or proof
of every pronounced word. Human listening and ASR were not performed. These files
are auditions, not approved releases; no audio is committed.

## Independent quality and security

PCM acceptance now rejects a dead left or right channel instead of mistaking
unequal one-sided audio for binaural stereo. Synthetic 16/24/32-bit measurements
and both dead-channel cases are covered. This strengthens validation without
changing signal generation or locked defaults; the actual Sleep Easy background
also passes the new per-channel acceptance checks.

The optional MCP SDK pin is updated from 1.28.1 to the compatible patched 1.30.0.
[GHSA-84m7-p3x7-pcfv](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-84m7-p3x7-pcfv)
affects stateful Streamable HTTP session retention, not OCF's stdio-only path.
Protocol tests use the patched SDK in an isolated environment. The running
OpenCode/MCP connection and its installed environment were not restarted or
reconfigured.
