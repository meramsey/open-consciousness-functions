# Editorial review and vocabulary boundaries

Current titles, spoken/display cues, lifecycle, commands, narration, and review
decisions are read from the canonical per-locale function resource. The derived
reports in `docs/releases/OCF_TITLE_CUE_CURRENT.*` and
`docs/releases/OCF_TEACHING_CURRENT.md` are reader views; they do not define
function content or retain predecessor wording.

## Approval boundaries

An editorial decision applies only to its recorded scope in
`record_metadata.editorial_approval` or `record_metadata.editorial_decisions`.
It does not imply historical authentication, rights clearance, listening
approval, or release readiness. Previous files and drafts are recoverable from
Git history, not from runtime archives or path-based replay helpers.

Editorial proposals remain data on the owning canonical locale resource and are
not active command or narration authorities. `status: pending` requires an
explicit human decision. Reviews of remaining vocabulary are handled one
function at a time; no batch promotion or automatic title/cue change is allowed.

```bash
python scripts/tools/current_title_cues.py --check
python scripts/ocf.py functions lookup "Mobius West" --locale en-US --json
python scripts/tools/check_hplus_narration_integrity.py
```
