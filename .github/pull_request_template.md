## Summary

<!-- One or two sentences: what does this change do? -->

## Type

- [ ] New function
- [ ] Function record change
- [ ] Command change (needs full rationale)
- [ ] Reimplementation proposal (incl. legacy source unavailable)
- [ ] Audio implementation / background preset
- [ ] Documentation
- [ ] Tooling / schema / tests
- [ ] Other

## Checklist

- [ ] `python3 scripts/ocf.py validate --all` passes (0 errors)
- [ ] All 55 legacy mappings are preserved (39 available / 16 unavailable)
- [ ] No generated file hand-edited (`python3 scripts/ocf.py build-index` used)
- [ ] Legacy commands preserved as metadata/aliases for any changed command
- [ ] `python3 scripts/ocf.py build-index --check` passes
- [ ] `python3 -m pytest` passes
- [ ] No copyrighted third-party audio/text added
- [ ] Safety and evidence statements follow `docs/SAFETY_POLICY.md` and
      `docs/EVIDENCE_AND_CLAIMS.md`

<!-- Command-change rationale (if applicable):
     legacy command / proposed OCF command / reason / word counts /
     compatibility strategy / review state -->

## Testing

What did you run to verify this change?

## Screenshots / examples

<!-- Optional: wizard transcript, generated index excerpt, output file. -->