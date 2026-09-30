# Proposals

RFC/PEP-style proposals for new functions, command changes, audio
implementations, and policy.

## Status workflow

```
draft -> review -> experimental -> accepted
                \-> rejected / withdrawn
accepted -> deprecated -> superseded
```

Proposal directories map to the lifecycle states:

| Directory      | Meaning                                          |
| -------------- | ------------------------------------------------ |
| `draft/`       | Being written; not yet under maintainer review   |
| `review/`      | Under review                                     |
| `accepted/`    | Approved                                         |
| `rejected/`    | Declined with reasons                            |
| `withdrawn/`   | Retired by the author before a decision          |

## Creating a proposal

Use the wizard:

```bash
./scripts/ocf new proposal
```

or copy `templates/proposal.md`, fill it in, and place it in `proposals/draft/`
as `ocfp-XXXX.md`.

## Proposal IDs

`OCFP-0001`, `OCFP-0002`, ... — the wizard assigns the next free number. IDs
are permanent; a rejected proposal's ID is never reused.

Proposals must address: problem, purpose, proposed name, command,
command-length rationale, activation, release, persistence, safety,
compatibility, evidence state, alternatives, implementation, testing,
sources, and licensing. All 16 source-unavailable legacy functions have an
open pathway to community reimplementation proposals.