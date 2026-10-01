# OCFP-0002: Semantic events, reusable stages and auditory bindings

- Status: draft
- Date: 2026-10-01
- Authors: OCF working group

## Problem

Keyed narration alone cannot coordinate DSP, nonverbal learned signals and
speech-dependent timing without conflating those layers. Preparation Learning,
Routine Preparation and Function Installation need shared structural stages.

## Purpose

Add extensible semantic identities, separate auditory references, versioned
stage inclusion and explicit timing anchors to the existing composer. Preserve
inline/slot/import behavior. No final narration or sound designs are supplied.

## Proposed name

Semantic events (`semantic`), auditory bindings (`auditory_cue`), reusable stages.

## Proposed command

No activation commands. Extend existing `ocf session compose --enable-stage`.

## Command-length rationale

Not applicable: no learned command is added or translated.

## Activation

Function records continue to own canonical activation commands.

## Release

Closing state cues and activation/release commands remain distinct.

## Persistence

Stage versions and instance identities are recorded on composed documents.

## Safety

No neurological claims, automatic learning claims or sound frequencies are
introduced. Cue designs, affirmation, tuning, visual identity and exact
Preparation Learning wording/timing remain TBD. Missing required narration
must block rendering rather than silently become prototype listener wording.

## Compatibility

Additive fields/schemas only; `cue_id` retains subtitle semantics. Imported
wording and contributor slots remain verbatim. Existing presets are preserved.

## Evidence state

Architecture implements the project requirements, not proprietary narration.
Functional structure may be informed by references; no source prose is copied.

## Implementation

See [semantic sessions](../../docs/SEMANTIC_SESSIONS.md). Runtime stage inclusion
and cue binding are implemented; cue playback, state-aware DSP synthesis and
the separate preparation toolchain remain unshipped. Listener exercises remain
architecture drafts until narration approval.

## Testing

`tests/test_semantics.py` verifies stage ordering, namespacing, optional stages,
profile replacement, future identities and language-independent structure.

## Sources

- Project narration/localization requirements and approved execution order.
- Existing `session-template.schema.json` and timed-transcript architecture.

## Licensing

Apache-2.0. No third-party narration or audio added.
