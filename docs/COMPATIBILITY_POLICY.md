# Compatibility Policy

Legacy compatibility is a hard requirement: historical commands, names, and
source-availability facts are research metadata and must never be deleted or
rewritten.

## States

| State           | Meaning                                                    |
| --------------- | ---------------------------------------------------------- |
| `unchanged`     | OCF canonical command equals the legacy command            |
| `alias-listed`  | Legacy command is retained as a documented alias           |
| `bridge-trainable` | OCF can *train an association* between legacy and canonical cues |
| `canonical-first`  | New situation uses the OCF cue first; legacy kept as alias |
| `legacy-first`  | Legacy cue kept first for now; OCF cue added later         |
| `none`          | No compatibility planned (rare; requires rationale)        |

## Principles

1. **Never silently delete a legacy alias.** Every changed command keeps its
   historical command in `legacy.commands` and in the command map indexes.
2. **Never claim automatic transfer.** OCF may design *bridge training* that
   associates a familiar legacy cue with the canonical OCF cue, but
   generalization is **not** presented as established science.
3. **Preserve unchanged good commands.** `PLUS-THINK`, `PLUS-FOCUS`,
   `PLUS-ENERGIZE`, `PLUS-RECALL`, etc. have `command_status: unchanged`.
4. **Changes need a documented reason.** See the change criteria in
   `docs/COMMAND_GRAMMAR.md`.

## Bridge training

A future bridge-training script may use an original OCF phrase such as:

> The familiar cue is [legacy command]. The concise OCF cue is [canonical
> command]. During this training exercise, either cue may be practiced with the
> same intended function.

This is a **training design**, not established science, and must be labeled as
such in scripts and documentation.

## Health and safety override

Compatibility never overrides safety. Emergency and health functions keep
their safety statements regardless of any legacy mapping.