# Governance

## Status

This project is in **early community bootstrap**. Governance is intentionally
lightweight until a contributor community forms; it will evolve by consensus
through proposals (see `docs/SUBMISSION_GUIDELINES.md`).

## Principles

1. **Open specification first.** OCF is a specification plus reference
   framework; code and audio tooling support the specification.
2. **Legacy compatibility is preserved.** Historical commands and mappings are
   retained as metadata even when the OCF canonical command changes.
3. **Code is minimal and auditable.** Few dependencies, deterministic output,
   generated files never hand-edited.
4. **No ungrounded claims.** Functions are labeled with an evidence state;
   health and emergency functions carry explicit safety notices.
5. **Independent by design.** OCF is not affiliated with The Monroe Institute
   or any related entity and must not imply that it is.

## Roles

| Role                 | Responsibility                                                        |
| -------------------- | --------------------------------------------------------------------- |
| Maintainers          | Review proposals, merge PRs, publish releases, steward permissions     |
| Reviewers            | Review proposals and PRs on specific domains                          |
| Contributors         | Author functions, proposals, audio, docs, and code                     |
| Users                | Practice, test, report issues, request documentation                   |

Permission is applied sparingly and only by the current maintainers.

## Decision-making

- **Requests for comments** follow the proposal lifecycle in
  `docs/FUNCTION_LIFECYCLE.md` with statuses `draft`, `review`,
  `experimental`, `accepted`, `deprecated`, `superseded`, `rejected`, and
  `withdrawn`.
- **Command changes** require the documented rationale in
  `docs/COMMAND_GRAMMAR.md` and `docs/NAMING_GUIDELINES.md` and are never
  silently applied to legacy data.
- **Breaking changes** to the schema require a proposal and a deprecation
  period.
- Disagreements are resolved by maintainer consensus; if none, by the Code of
  Conduct and community review.

## Contact

Currently no dedicated contact address exists. Use GitHub issues for questions
and proposals. Security reports: see `SECURITY.md`.