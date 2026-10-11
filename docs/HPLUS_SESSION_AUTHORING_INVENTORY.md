# Human Plus session authoring: current source-to-render inventory

Status: inventory of the pipeline, initially recorded 2026-10-08. This document
does not authenticate any historical source or approve narration. User-supplied
reference material and source-first working snapshots remain local. The shared
resource migration described below is now versioned separately; its editable
locale files supersede local preview wording snapshots.

## Direct answer

There is **not one full, tracked OCF script per each of the 55 mapped
functions**. The original transcripts are local input under
`references/HumanPlusTranscripts/`. The 55 canonical function identities and
the source analysis that points into those files are tracked under `functions/`
and `function-content/`. Exact source snapshots and source-first block drafts
for all 55 are in the ignored `.ocf-authoring/` workspace (39 source snapshots;
16 records remain source-unavailable). Only Attention currently has a complete
tracked timed-session path: the citation-only import `audio/scripts/attention.yaml`,
the Attention session template/slot, the composed `audio/scripts/attention-ocf.yaml`,
and `audio/manifests/OCF-AUDIO-0001.yaml`.

For the recent all-function audition, the full local files actually used were
the block/source records in `.ocf-authoring/` plus the local-only scripts
`.ocf-authoring/build-full-function-working-auditions.py` and
`.ocf-authoring/build-reconstruction-mockup-auditions.py`. Those scripts wrote
auditions under ignored `audio/rendered/auditions/full-functions-working/` and
`audio/rendered/auditions/reconstruction-mockups/`; those are personal WIP
renders, not `audio/scripts/` sources consumed by `ocf audio build`.

The source-to-render flow therefore has two distinct paths today:

```text
Source-first research path (all 55 mappings):
  local references/HumanPlusTranscripts/
  → tracked function-content evidence/specification locators
  → ignored .ocf-authoring source snapshots + candidate blocks
  → [currently no shared canonical full-session script for each function]

Official Attention build path:
  local Attention LRC imported as ignored audio/scripts/attention.yaml
  → tracked OCF-TPL-SESSION-ATTENTION-001 + audio/slots/attention/focus11.txt
  → tracked composed audio/scripts/attention-ocf.yaml
  → tracked audio/manifests/OCF-AUDIO-0001.yaml
  → ocf audio build → ignored audio/rendered/OCF-AUDIO-0001-* and
    audio/rendered/OCF-RENDER-0001.yaml
```

The source-first boundaries are explicitly **candidate** semantic partitions,
not a runtime authoring contract. They are not automatically promoted into the
Attention template or any function audio manifest.

## File/path inventory

| Repository path | Source-of-truth / role | Git status | Controls / is used by |
| --- | --- | --- | --- |
| `references/HumanPlusTranscripts/+Transcripts From available tapes/*/` | User-supplied `.txt`, `.srt`, `.lrc`, OCR PDFs and associated notes; available transcript text is unauthenticated or partial as marked in sidecars | Untracked user input; read-only, not committed | Research/source input only. It is not a runtime package resource. |
| `references/HumanPlusTranscripts/<function>/*_reconstructed_clean.txt` and `*_reconstructed_annotated.txt` | Explicit reconstructions/mockups, not recovered transcripts | Untracked user input; not committed | Separate local reconstruction candidates. Does not change the 16 canonical source-unavailable statuses. |
| `references/HumanPlusTranscripts/Preparation/PreparationExample{1,2,3}.txt` | User-selected preparation examples; authentication/completeness remain unverified | Untracked user input; not committed | Local Preparation Learning text review. Example 2 remains separate from the Example 1/3 basis. |
| `functions/**/*.yaml` | Canonical 55 function identities, commands, availability, safety and reimplementation status | Tracked | Discovery/ownership metadata; not full narration scripts. Keep all 16 unavailable records `planned`. |
| `function-content/{evidence,specifications,decisions,bindings}/OCF-*.yaml` | Hash-addressed observations, exact source extents, candidate section locators, OCF decisions and bindings | Tracked | Analytical/provenance sidecars. They do not authenticate source, approve wording, or define runtime state timing. |
| `.ocf-authoring/functions/OCF-*.yaml`, `.ocf-authoring/sources/*.yaml`, `.ocf-authoring/blocks/*.yaml` | Exact SOURCE snapshots and initial WORKING blocks; candidate semantic partitioning | Ignored local workspace; 55 skeletons, 39 available source snapshots, 16 source-unavailable skeletons | `ocf content` workspace/review only. Not imported by `ocf audio build`, not packaged. |
| `.ocf-authoring/preparation-learning-shared-defaults.yaml` | Previous human-selected local preparation wording defaults, including explicit edits | Ignored local workspace | Preparation Learning WIP only; not a global function-session template. |
| `audio/scripts/attention.yaml` | Citation-only imported Attention LRC snapshot | Ignored by `.gitignore`; protected from editing | Local source/timing input; do not hand-edit. |
| `audio/scripts/attention-timing-template.yaml` | Timing-only Attention transcript template | Tracked | Interoperability/legacy timing reference; not a generic function template. |
| `audio/scripts/attention-ocf.yaml` | Composed OCF Attention script | Tracked | Full script consumed by `OCF-AUDIO-0001`; regenerate only through session composition. |
| `audio/templates/sessions/OCF-TPL-SESSION-ATTENTION-001.yaml` | Attention-only adapted legacy-arc session template | Tracked | Fixed Attention structure/timing. One `focus11` slot repeats twice in Focus 11 and via `from_slot` twice at `gain_db: -24` in the sleep-20 section. |
| `audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml` | Generic four-slot learn-session shell | Tracked, `architecture-draft` | Requires separate `opener`, `focus11`, `sleep20`, `closer` files; fixed absolute section starts/default duration. It does not bind the sleep slot to the Focus 11 slot. |
| `audio/templates/sessions/OCF-TPL-SESSION-PREP-LEARN-001.yaml` and `...PREP-ROUTINE...` | Preparation Learning / routine templates | Tracked | RC1 learning/recall shells; not legacy function-body templates. |
| `audio/templates/stages/OCF-TPL-STAGE-*.yaml` | Versioned semantic stages (orientation, setting aside, relaxation, F10, F11 open/close, return, affirmation, tuning, etc.) | Tracked | `ocf session compose`; many stages have narration keys and measured speech-end dependencies. No shipped Energy Ball stage is present. |
| `audio/slots/attention/focus11.txt` | Attention function instruction slot | Tracked | Attention template slot only; not a 55-function registry. |
| `locales/en-US/functions.yaml` | OCF-owned keyed function narration resources | Tracked | Localized OCF wording and stage overrides, not historical Human Plus source text. |
| `audio/voices/profiles/piper-lessac.yaml` | Piper profile `OCF-VOICE-0002`; model path is operator-local | Tracked | Selects Piper/en-US/model. `words_per_min: null`; it does **not** encode the slow-session profile values. |
| `audio/voices/profiles/piper-lessac-slow.yaml` | Piper profile `OCF-VOICE-0003` | Tracked, draft | Uses the locally selected `length_scale: 1.12` and `sentence_silence: 0.4`; still operator-local model/executable. |
| `audio/background/state-profiles/OCF-DSP-DEFAULT-001.yaml`, `OCF-DSP-DEVELOPMENT-V4-*.yaml` | Semantic DSP state-to-preset mappings | Tracked | `ocf audio build --dsp-profile`/`render-state-program`; default binds F11 only. V4 induction profile binds F10 candidate + F11, not Focus 20. |
| `audio/manifests/OCF-AUDIO-0001.yaml` | Attention audio implementation manifest | Tracked | Points to `audio/scripts/attention-ocf.yaml`, Piper profile, and static `OCF-BG-0011` reference-master bed. |
| `audio/scripts/<slug>.yaml` | Canonical timed narration input | Tracked if committed | `ocf voice render` / `ocf audio build`. No per-function script exists here for the other 54 mappings. |
| `.ocf-authoring/build-full-function-working-auditions.py` and `.ocf-authoring/build-reconstruction-mockup-auditions.py` | Recent local audition generators | Ignored local scripts | Piper 1.12 block TTS, candidate role timing, F10/F11 state-stem mix, 598.68-second WIP sleep hold and quiet repeat. Not the official `ocf` renderer path. |
| `audio/rendered/` | Narration stems, auditions, masters, timing/render manifests, SRT/LRC/VTT exports | Ignored generated output | Outputs of local working scripts and `ocf audio build`; never an authoring/source location. |
| `scripts/ocf_tools/session.py`, `transcript.py`, `voice.py`, `semantic_dsp.py`, `audio_build.py` | Session composition, timeline/import/export, TTS, semantic DSP and build/mix implementation | Tracked | Official pipeline. Entry point is `scripts/ocf.py`; `session.compose` writes timed YAML, `voice.render_narration` measures cue speech, `audio_build.build` makes stems/master/render manifests. |

## Current official generation and exports

`ocf session compose` reads one tracked session template and contributor slots,
then writes a canonical timed document (by default under `audio/scripts/`).
`ocf voice render` synthesizes each cue, measures its duration, resolves `after`
anchors, and writes a mono PCM WAV plus a `.render.yaml` timing sidecar. `ocf
audio build` reads the script path from an audio manifest, renders narration,
uses either the manifest’s static background or a semantic DSP profile, mixes,
and writes WAV/FLAC/MP3 plus `OCF-RENDER-*.yaml`. `ocf transcript export`
separately creates SRT/VTT/LRC; measured end-dependent anchors require the
render manifest. These official stages do not currently consume the 55
`.ocf-authoring` function skeletons.

## Diagnosed causes of inconsistent pacing and wording

1. **No shared session is bound to the 55 functions.** Only Attention has a
   composed full script and audio manifest; the 55 function records have no
   `audio/scripts/<function>.yaml` bindings. Function-specific narration is
   therefore assembled in local one-off workflows.
2. **The two existing session templates have different contracts.** The generic
   Learn template has separate required opener/Focus 11/sleep-20/closer slots,
   defaults `line_seconds: 3` and `duration: 1800`, and hard-coded section
   starts. The Attention template has one function slot, uses it for two
   Focus-11 passes and two Focus-20 underlay passes, and has its own fixed
   legacy-derived timing. These are not one shared template/pacing policy.
3. **Untimed slot pacing is synthetic.** `session._parse_slot` spaces untimed
   lines by `line_seconds` or evenly across a fixed section. This is unrelated
   to actual Piper speech duration. The slot composer does not measure TTS.
4. **TTS settings differ by route.** `OCF-VOICE-0002` has no WPM or Piper
   length-scale/sentence-silence values. The recent local auditions used direct
   Piper calls at 1.12/0.4; official `voice.py` invokes Piper without those
   arguments. Different routes therefore cannot be expected to match pace.
5. **Source variation is being treated as if it were one wording.** The local
   analysis has 39 source snapshots, but the exact SOURCE/WORKING block report
   has 39 distinct preparation blocks, 38 opener variants (only two exact
   duplicates), 53 closer variants among 66 occurrences, and 38 distinct
   consolidation blocks. Similarity labels are candidates only. Standardizing
   them requires an explicit human selection, not automatic normalization.
6. **State ownership is not bound consistently.** The Attention script has
   legacy absolute timestamps; V2.1 has a separate measured semantic ledger and
   DSP program; the recent all-function audition helper used candidate block
   roles and a local mix. No common function template currently connects a
   single body reference to measured Focus-11 and Focus-20 repetitions.

The inventory does not alter or regenerate `audio/scripts/attention.yaml`, the
RC1/V2/V2.1 auditions, source references, function mappings, or the local
source-first workspace.

## Draft shared-session architecture and review candidates

The new reusable candidate is
`audio/templates/sessions/OCF-TPL-SESSION-HPLUS-STANDARD-001.yaml`, with the
versioned pacing policy
`audio/templates/pacing/OCF-PACING-HPLUS-STANDARD-001.yaml`, shared HPlus
semantic stages in `audio/templates/stages/`, and the draft DSP mapping
`audio/background/state-profiles/OCF-DSP-HPLUS-STANDARD-DRAFT-001.yaml`.
It accepts only function-specific `opener`, one `function_body` resource, and
`closer` slots (plus disabled optional-stage slots). The same function-body
resource is referenced twice in Focus 11 and twice at the candidate -24 dB gain
in Focus 20. Focus 20 DSP remains disabled by default. The pacing policy's
60-second Focus 10 hold, 600-second Focus 20 lead-in, repeat gaps, 160 wpm
estimate, and gain are draft design values, not recovered historical timings or
efficacy claims. The Piper session profile records the locally selected 1.12 /
0.4 slow settings.

The shared narration is now selected in one canonical locale file per reused
section; see [HPlus narration resources](HPLUS_NARRATION_RESOURCES.md) for the
editable files, source locators and user-cleared rights attestation. The
standard template is version 1.0.0 with `content_status: draft`, because
function-specific review and measured timing remain pending. Optional stages
remain disabled. `ocf session compose --function ID --locale TAG` binds the
function's three locale keys; `--pacing-profile` overrides the versioned policy.

Three local preview/ledger pairs were generated for representative cases:

| Function | Source status | Review dimension |
| --- | --- | --- |
| `OCF-FND-002` Attention | `transcript_unverified` | short source-backed function body and baseline comparison with the existing official Attention route |
| `OCF-SLP-002` Sleep | `transcript_unverified` | longer function body and sleep-oriented use case |
| `OCF-BOD-002` Circulation | `partial_transcript` | distinct function with partial-source evidence and explicit incompleteness |

The outputs are ignored under
`.ocf-authoring/previews/hplus-standard-review/`; the local generator is
`.ocf-authoring/build_hplus_standard_previews.py`. Each preview combines that
function's dedicated locale resources with the shared canonical locale wording.
Each ledger gives semantic IDs, source locators,
word counts, estimated timings, repetition anchors, and the Focus 20 gain. The
160 wpm times are planning estimates only; no TTS measurement or audio render
was run. Attention-derived shared wording is a human-selected OCF resource,
not an assertion of a universal historical transcript. The generated previews
remain local review artifacts; their editable wording now lives in locale files.

Shared wording uses the approved Transmutation Box edit and the user's
body-part relaxation segmentation. Rights are user-cleared; authentication
remains unverified. All 55 function-specific English review files are now present;
see [the review list](HPLUS_FUNCTION_REVIEW.md). Of the 39 source-available
functions, 28 have all three historical extents selected and 11 have historical
source gaps. The 16 source-unavailable functions have separately labeled
user-proposed reconstruction drafts. Five OCF-authored suggestions separately
address source gaps, giving 49 files with all three review slots populated; the
Access to Information closer remains pending approval. Historical source
availability and planned reimplementation status are unchanged. Human wording
review remains pending for entries marked draft.
Focus 20 underlay audibility, long holds, and localized speech timing need
measurement/listening review before finished audio release.
