# Previously approved editorial proposals

Manifest (`OCF-EXP-001`), Dissolve (`OCF-EXP-003`), Intuition (`OCF-EXP-006`),
and Clear Zone (`OCF-EXP-005`) were approved for implementation. They are now
registered functions; their words, commands, procedures, and editorial approval
hashes live in their respective canonical locale resources. No candidate YAML or
working copy is an active authority.

| Function | Canonical resource |
| --- | --- |
| Manifest | [`OCF-EXP-001`](../locales/en-US/OCF-EXP-001-Manifest.yaml) |
| Dissolve | [`OCF-EXP-003`](../locales/en-US/OCF-EXP-003-Dissolve.yaml) |
| Clear Zone | [`OCF-EXP-005`](../locales/en-US/OCF-EXP-005-Clear-Zone.yaml) |
| Intuition | [`OCF-EXP-006`](../locales/en-US/OCF-EXP-006-Intuition.yaml) |

The embedded `record_metadata.editorial_approval` objects preserve the approval
decision, source revision, presented-snapshot digest, resolved-text digests, and
the limits of approval. The digests are verification metadata only and cannot
provide or resolve alternate function content.

Preview the canonical resource without creating another source file:

```bash
python scripts/ocf.py functions candidates --json
python scripts/ocf.py functions candidates intuition --preview
```

These approvals do not imply listening approval, rights clearance, or release
readiness. See [editorial approval boundaries](EDITORIAL_BATCH_APPROVAL.md).
