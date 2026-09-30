# Function Lifecycle

Every function (and proposal, and command change) moves through an RFC/PEP
style lifecycle.

## States

```
        ┌──────────────────────────────────────────┐
        │                                          ▼
   draft ──► review ──► experimental ──► accepted ──► deprecated ──► superseded
     ▲        │                │
     └────────┴──► rejected / withdrawn
```

| State        | Meaning                                                     |
| ------------ | ----------------------------------------------------------- |
| `draft`      | Being written; not binding                                  |
| `review`     | Under maintainer/community review                           |
| `experimental` | Approved for structured experimentation (labeled)         |
| `accepted`   | Canonical; commands may be marked `approved`                |
| `deprecated` | No longer recommended; metadata preserved                   |
| `superseded` | Replaced by another record; `supersedes` recorded           |
| `rejected`   | Declined with recorded rationale                            |
| `withdrawn`  | Retired by the author before decision                       |

## Where states live

- **Proposals**: `proposals/{draft,review,accepted,rejected,withdrawn}/` with
  a `status:` line.
- **Function records**: `status.maturity` (e.g. `legacy-mapped`,
  `community-proposed`, `accepted`) and `ocf.command_review`.
- **Audio implementations**: `review_state`.

## Command review states

| State            | Meaning                                            |
| ---------------- | -------------------------------------------------- |
| `pending`        | No decision yet                                    |
| `approved`       | Canonical command decided                          |
| `needs-review`   | Normalized; awaiting confirmation                  |
| `review-required`| Proposed; must not be treated as approved          |
| `superseded`     | Replaced by an earlier/later decision              |

## Who decides

- Draft: anyone.
- Review→experimental→accepted: maintainer review per `GOVERNANCE.md`.
- Command canonicalization: requires the change record and rationale.
- Deprecation: requires a proposal; records are never deleted.

## Stability guarantee

IDs are permanent and survive renames. Historical records are never removed —
only deprecate, supersede, or reject.