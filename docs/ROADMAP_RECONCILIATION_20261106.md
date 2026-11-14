# Roadmap reconciliation — 2026-11-06

## Inputs and preservation

The complete `ROADMAP.md` at `b7fefd1` is the preservation baseline, including
its three previously added editorial review items. This reconciliation expands
those three in place and adds two engineering items; it does not replace the
backlog with the latest request or infer completion from proposals.

Reviewed planning/continuity inputs include the generated reimplementation
roadmap (all 55 legacy identities), preparation-module design, authoring-plan
guidance, documentation workflow map, production-supervision contract and the
Phase2C continuation checkpoint dated 2026-10-02. Older checkpoint counts and
statuses are historical evidence, not fresh measurements. No tracked TODO file
was found by Git's inventory. Current ROADMAP checkbox states are retained.

The public GitHub API open-issue/PR inventory at reconciliation time returned
PR 27 (single-source migration) and PR 18 (pypdf dependency update), with no open
standalone issue duplicating the five additions. PR 27 is open without submitted
reviews; its historical head `0a408a56cdc8fbf6af219879d0b021def995d308`
has successful CI. The dependency PR is unrelated and unchanged. Issue/PR
creation is unavailable through the unauthenticated GitHub CLI in this session;
these items are therefore recorded directly in the actual Git-tracked roadmap,
not represented as nonexistent GitHub issues.

## Reconciliation decisions

- Keep all original version sections, approved additional backlog, private audio
  and voice work, proposed functions, post-v1.0 intelligibility and non-goals.
- Keep unit-only 100% coverage as an unmet longer-term goal, distinct from the
  mandatory combined 89.5% statement / 84.0% branch floors. Performance work
  cannot reduce either obligation or shrink meaningful exercised behavior.
- Keep broad preparation-stage/CLI goals unchecked: shipped reusable mechanics
  do not mean the dedicated preparation product, wizard or listening approval
  is complete. Short/long relaxation is not the same as omitting expert stages.
- Keep native runtime/adapter verification open while acknowledging historical
  cross-platform Python CI; CI success does not prove private engines or audio.
- Keep broad shared-workspace migration, voice portability, production rollout,
  ownership and cleanup work unchecked despite existing helpers/deployments.
  Their end-to-end acceptance and private asset migration must still be verified.
- Clarify checked migration milestones: localized canonical resources own IDs,
  command controls and embedded content. Generated technical maps and historical
  provenance are not editable authorities; predecessor path readers are retired.
- Keep A4 favorable feedback, A5 pending listening and all private publication
  restrictions unchanged. No favorable audition or technical QC becomes release
  permission. Nutricia convenience is not a weight-loss guarantee.
- Expand TODO A/B/C rather than duplicate them; add TODO D/E with priorities,
  reproducible measurements, acceptance, dependencies and implementation order.

The separate documentation branch is stacked on the existing roadmap checkpoint
and PR 27's historical head, not mixed into PR 27's authoring fixes. It must not
be merged around PR 27's required review authorization.
