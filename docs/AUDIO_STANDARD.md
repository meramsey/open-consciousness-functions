# Audio Standard

Defines how OCF represents audio implementations.

## Scope

Audio is **optional**, never required for a function to be a function. A
function may have several audio implementations; implementations are concrete
manifests, not the function itself.

## Manifest (`schemas/audio-implementation.schema.json`)

| Field                        | Meaning                                  |
| ---------------------------- | ---------------------------------------- |
| `id` / `function_id`         | Permanent IDs                            |
| `title` / `version`          | Identity                                 |
| `contributor` / `narrator`   | Attribution                              |
| `language` / `license`       | Legal / locale metadata                  |
| `training_type`              | One of 8 allowed types                   |
| `duration_minutes`           | Length                                  |
| `induction`                  | How the session opens                    |
| `command_rehearsal`          | Canonical cue rehearsal language         |
| `legacy_bridge`              | Optional legacy-cue bridge design        |
| `mode_rehearsal`             | Directional mode rehearsal text          |
| `release_rehearsal`          | Release/cancel rehearsal                 |
| `safety_intro`               | Required safety opening                  |
| `transcript_path`            | Link to the script                       |
| `background_audio`           | Strategy + preset reference              |
| `technical`                  | Sample rate, channels, format(s), tags, loudness, checksum |
| `testing_notes`              | Anecdotal observations                   |
| `review_state`               | Lifecycle state                          |

## Training types

`training` · `reinforcement` · `quick` · `sleep` · `extended` · `voice-only` ·
`background-only` · `experimental`

No single style is required. A `quick` reinforcement is as valid as a full
`extended` induction.

## Structure recommendations

A conventional training script:

1. safety intro;
2. induction / settling;
3. canonical command rehearsal (with modes as applicable);
4. optional legacy bridge rehearsal (labeled as a training design);
5. practice / imagery window;
6. release rehearsal.

## Safety

Every implementation records a `safety_intro` (see `SAFETY_POLICY.md`), and
technical metadata includes loudness notes for accessibility. Rendered files
get their SHA-256 recorded in `technical.checksum_sha256` for provenance.

That checksum identifies **the artifact that was built**, not a reproducible
recipe. TTS backends are not bit-exact: rendering the same line with the same
Piper model and settings three times in a row produced three different
SHA-256 digests and slightly different durations (measured 2026-09-29). Treat
`technical.checksum_sha256` as an identity record for one master file, and use
the script, the voice profile, and the render manifest to describe how it was
produced. Do not claim a rebuild reproduces the same bytes.

## Outputs and metadata tags

`ocf audio build` emits the WAV master plus FLAC and MP3 derivatives by default
(`--format` is repeatable and accepts `wav|flac|mp3`). Every FLAC/MP3 file is
tagged with metadata derived from the manifests — `title`, `artist`, `album`,
`track`, a `comment` noting the OCF generator and citation-only/synthesized
nature of the narration, plus OCF namespaced tags (`OCF_AUDIO_ID`,
`OCF_FUNCTION`, `OCF_COMMAND`, `OCF_AUDIO_VERSION`, `OCF_NARRATOR`,
`OCF_GENERATOR`, `OCF_TIMING_MODE`, and `OCF_SESSION_TEMPLATE` when the script
was composed from a session template). Any tag can be overridden with repeated
`--tag KEY=VALUE`. The render manifest records every output file, its format,
encoder, checksum, and the tag set used. WAV stays untagged (plain PCM); use
the render manifest as its metadata record.

## Background reuse

`background_audio.preset` references an `OCF-BG-*` manifest. Backgrounds are
shareable across functions; see [`BACKGROUND_AUDIO.md`](BACKGROUND_AUDIO.md).

## Scripts and timed transcripts

The spoken narration for an audio implementation is authored as an **OCF timed
YAML** script stored in `audio/scripts/<slug>.yaml` and referenced by
`transcript_path` in the manifest. Common timed narration is also available in
**timed-lyrics / LRC** (import), **SRT** (import + export), **WebVTT**
(import + export), and plain **txt / md** (untimed import); `ocf transcript
import` converts all of these to canonical OCF timed YAML without rewriting the
source text.

OCF timed YAML supports:

- absolute timestamps (`at`) and relative timestamps (`after` + `offset`);
- per-segment `voice`, `gain`, `pause_after`, and `timing` constraints;
- flat top-level timelines and grouped `sections` with reusable roles;
- per-segment state/focus annotations (see [`docs/TIMED_TRANSCRIPTS.md`](TIMED_TRANSCRIPTS.md)).

The transcript toolchain (import / analyze / segment / review / export /
extract-template) and the narration/audio-building toolchain (`ocf voice …` /
`ocf audio …`) are **shipped**; see `docs/TIMED_TRANSCRIPTS.md`. The normative
specification is `OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`
(§32, §44–§50).