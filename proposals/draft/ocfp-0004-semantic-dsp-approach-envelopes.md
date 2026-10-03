# OCFP-0004: Supporting DSP approach independently of semantic arrival

- Status: draft additive scheduling implementation
- Date: 2026-10-02

Semantic state is not DSP onset. Profiles may explicitly bind an`approaches`
entry to three existing event occurrences: begin, established and state directive.
The selected target program emerges before state arrival without changing state
identity, narration, timing anchors or physical signal parameters. All anchors
resolve from the actual narration/event ledger, never English wording or filenames.

An approach must end no later than its owning state directive, which must actually
select its configured target. It cannot overlap another state change or approach,
refer to missing/duplicate/nonfinite anchors, or quietly substitute a disabled/
unrelated state. On arrival the state envelope continues at established gain,
rather than replaying a fallback ramp. Existing profiles without this optional
field retain exactly their prior gain behavior. Subsequent transitions/holds/exits
reuse the existing dispatcher. No semantic identities or source evidence changed.

The first development profile uses zero-to-one raised-cosine amplitude (zero
endpoint slopes) during progressive relaxation through spoken Ten. The curve
is an explicit OCF envelope choice, not measured V4 signal design or subjective
mastering approval. V2 remains preserved for comparison with V2.1.
