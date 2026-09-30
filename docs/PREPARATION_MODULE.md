# Preparation Module

Status: **planned** (v0.4/v0.5, tracked in `ROADMAP.md`). The `ocf preparation
…` group is specified in
`OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`
(§51–§55) but **not yet shipped**. This document is the design target and the
home for the planned **composable preparation stages** (relaxation, Energy
Conversion Box, optional affirmation, optional oHm / resonant-tuning chant,
Focus 10 transition, `focus11_open` / `focus11_ready`). Nothing here is
implemented until a live command exists.

## Normative anchors

- §51 — preparation track as a first-class artifact
  (`preparation/{README.md,modules/,templates/,manifests/}`,
  `schemas/preparation-module.schema.json`, `templates/preparation-module.yaml`,
  IDs `OCF-PREP-*`).
- §52 — source-reference import workflow (`ocf preparation import-reference`)
  builds an **original OCF** template scaffold, not copied prose.
- §53 — wizard (`ocf new preparation`); per-section choice of default OCF
  wording / edit / custom / import-for-timing / freeform / **omit optional
  section**.
- §54 — preparation dependency model: `training_requirements.preparation`
  (`required`, `module`, `completion_model`:
  `learn-once · recommended-refresh · per-session · none`) and
  `assumes_preparation_installed` / `includes_preparation_refresh` on audio
  implementations.
- §55 — session composition templates (`OCF-SESSION-FUNCTION-LEARN-001`,
  `…-REFRESH-001`, `…-PREPARATION-001`, `…-FREEFORM-001`).

This extends the timeline already shipped for section composition into the
preparation role: the shipped `OCF-TPL-SESSION-*` shells (§46/§55, see
`docs/TIMED_TRANSCRIPTS.md`) are the mechanics; preparation is a specific
composition of them.

## Decided requirements

1. **Composable, not monolithic.** Preparation is a pipeline of stages, each
   optional and independently composable. No stage hardcodes another stage's
   wording, and no new session duplicates audio-generation code to pick a
   subset of stages.
2. **Canonical stage order** for the standard track:

   ```text
   relaxation → Energy Conversion Box (set aside distractions)
   → [optional affirmation] → [optional oHm / resonant-tuning chant]
   → Focus 10 transition → focus11_open → focus11_ready → function/exercise
   ```

   The template builder supplies relaxation and Energy Conversion Box
   mechanics today (`OCF-TPL-SESSION-ATTENTION-001` already contains
   Energy Conversion Box wording); the optional affirmation and oHm stages
   slot in *between* the Energy Conversion Box and the Focus 10 transition.
3. **Affirmation stage** (optional). Supports: disabled / built-in default
   text / user-supplied text / multi-block affirmation / TTS via the
   configured backend / pre-recorded (user or bundled) audio / configurable
   pause before and after. Future wizard selection is planned.
4. **oHm / resonant-tuning chant** (optional). Supports: disabled / bundled
   OCF default / generated chant / user recording / call-and-response with
   configurable repetitions or duration. The chant itself is a
   **language-independent vocal sound**; any surrounding spoken instruction is
   localized through the locale layer (`docs/LOCALIZATION.md`).
5. **No behavior change by default.** All new stages default to
   disabled/absent so existing presets, scripts, templates, and audio
   implementations rebuild identically.
6. **Wording policy.** All shipped preparation stages are **original OCF
   wording**. Reference/preparation imports stay citation-only; timing-only
   scaffolds may be extracted from them but prose is never copied (§52,
   `AGENTS.md`).

## Proposed architecture

All concrete schema/field names are **proposals (TBD)**; they require a
proposal (`OCFP-*`) and coordinated schema/template updates per
`docs/DESIGN_SPEC.md`.

### Stage model

A preparation module is a list of sections (reusing the shipped section/role
model in `schemas/timed-transcript.schema.json` and the reusable section
templates planned as `audio/templates/preparation/` in §46). Each stage:

- has a **role** id (`relaxation`, `ecb`, `affirmation`, `ohm`, `focus-10`,
  `focus11-open`, `focus11-ready`, …);
- is **optional** and has a cleared default (absent = skipped);
- carries `source: template` (an `OCF-TPL-PREP-*` reusable section), `custom`,
  `user-audio`, or `freeform`;
- may declare an optional **audio asset** path (affirmation/oHm pre-recorded),
  otherwise it is rendered through the TTS voice layer — a
  language-independent decision made at render time via
  `docs/LOCALIZATION.md`.

The stage pipeline composes into a session the same way `ocf session compose`
composes slots today: a `OCF-SESSION-PREPARATION-001` (or the existing
`OCF-TPL-SESSION-*` shells) declares required + optional stage roles, and the
composer emits only the enabled stages in order.

### Targeting

- **Short / expert** preparation = enable `focus-10`/`focus11-open`/
  `focus11-ready` only (or none, with `assumes_preparation_installed: true`).
- **Standard** = all stages, the OCF default track.
- **Custom** = any subset in canonical order.
- **Localized** = same stage set, per-locale wording (`docs/LOCALIZATION.md`).
- **Function-only / chained-function sessions** = preparation omitted or
  reduced per `training_requirements` (§54): `learn-once` default, plus
  `recommended-refresh` / `per-session` where source review supports it.

## Versioning and backward compatibility

- New stage roles default to **skipped**; `timing_mode`, `gain_db`, and the
  render contract are unchanged for existing sessions.
- Preparation module and session-template records get explicit version fields
  so a changed stage set is a new version, never a silent rewrite of the old
  one (mirrors the audio-implementation `version` field).
- Adding fields to `training_requirements.preparation` and to
  `schemas/preparation-module.schema.json` follows the proposal process and is
  additive (optional) only.

## Open questions (TBD)

- Exact `ocf preparation` CLI surface beyond §53's listed commands (compose
  aspects vs `ocf session compose` reuse).
- Whether affirmations/oHm are separate reusable section files
  (`audio/templates/preparation/`, OCF-TPL-PREP-*) or inline stage options.
- Call-and-response timing contract for the oHm stage (leader line vs
  breathing window) — TBD design, not a claim about effect.
- Whether generated chant audio must be asserted original-OCF (it is an OCF
  render, not a recording of a third party) — documented per
  `docs/SOURCE_ATTRIBUTION.md`.

## Integration points

- `schemas/timed-transcript.schema.json` — `section.type` already includes
  `preparation`; `sections[].background`/`gain_db`/`state` support the DSP
  and focus transitions.
- `schemas/session-template.schema.json` and `scripts/ocf_tools/session.py` —
  shipped declared-slot composition is the mechanism stages compose into.
- `docs/LOCALIZATION.md` — all preparation narration is localized text;
  stage structure and the chant/sound layers are language-independent.
- `docs/TIMED_TRANSCRIPTS.md` — status matrix, quiet sections, and the
  planned focus-state cue events (`focus11_open`, `focus11_ready`,
  `session_complete`) pair with the parallel stages here.
- `docs/ARCHITECTURE.md` — planned `preparation`/`locale` tooling layers sit
  beside the existing `session`/`voice`/`audio` handlers.