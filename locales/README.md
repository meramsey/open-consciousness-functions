# Locale packs

Each locale is one directory holding a manifest and one or more resource files:

```
locales/
  en-US/
    manifest.yaml
    ui.yaml            operator- and player-facing strings
    narration.yaml     listener-facing spoken narration
    functions.yaml     per-function narration templates
  es/
    ...
```

`en-US` is the canonical locale: new narration keys are authored there first,
and every other pack is filled from it. That is why English is *data* here too,
not a special case baked into the code.

## Adding a language

1. Copy `locales/en-US/` to `locales/<tag>/`.
2. Set `locale`, `language_name`, and `status` in the manifest. A pack is
   `machine` until a speaker of that language has reviewed it.
3. Set `translation.source_locale: en-US` and
   `translation.source_semantic_version` to the version you copied.
4. Translate the entries. Leave a key out rather than copying the English string
   if you have not translated it — a missing key fails the strict spoken check,
   which is the honest signal. Copying English would hide it.
5. `ocf locale validate` — fix variable-contract errors before anything else.
6. `ocf locale resolve --session audio/templates/sessions/OCF-TPL-SESSION-FOCUS-CYCLE-001.yaml --locale <tag>`
   to see the session in that language.

## Manifest

| Field                              | Meaning                                                   |
| ---------------------------------- | --------------------------------------------------------- |
| `locale`                           | BCP-47 tag, e.g. `en-US`, `es`, `zh-Hans-CN`               |
| `language_name`                    | Endonym shown to operators                                |
| `direction`                        | `ltr` or `rtl`                                            |
| `status`                           | `canonical`, `draft`, `machine`, `reviewed`               |
| `semantic_version`                 | Semver for the *meaning* of the keys (see below)          |
| `translation`                      | Source locale/version, translator, review date, notes     |
| `resources[]`                      | `file`, `domain` (`ui` or `narration`), `description`     |
| `plural_rules`                     | Optional CLDR-style overrides for this language           |

## Entries

An entry is either a plain string (when the message has no variables, status, or
pronunciation to record) or a mapping:

```yaml
entries:
  session.focus-cycle.opener: "Welcome to the Open Consciousness attention function."

  function.repetition.count:
    text: "{count, plural, one {# repetition} other {# repetitions}}"
    variables: [count]
    status: machine
    version: "1.0.0"
    pronunciation:
      espeak-ng: "repetitshon"
    notes: "Translator: check the stress on the second syllable."
```

Keys are lowercase dotted kebab-case. Author them for what the line *does*, not
for what it says — `session.focus-cycle.tenth-state.enter`, not
`now-we-enter-the-tenth-state`.

### Message syntax

A documented subset of ICU MessageFormat:

| Syntax                             | Use                                       |
| ---------------------------------- | ----------------------------------------- |
| `{name}`                           | Substitute a variable                     |
| `{n, plural, one {…} other {…}}`   | Select a whole branch by plural category  |
| `{n, selectordinal, one {…} other {…}}` | Ordinals (1st, 2nd, 3rd)             |
| `{n, select, female {…} other {…}}`| Select a branch by an exact value         |
| `#`                                | The plural value, minus `offset:`        |
| `'{'`                              | Quote a literal brace                     |
| `\#`                               | A literal `#`                             |

Branches are always whole sentences. Word order, punctuation, and gender all
come from the message; the runtime never assembles a sentence from fragments,
because that is how languages with different word order get mangled.

`variables` must list exactly what the message uses. A mismatch is an error, not
a warning: it is the difference between a translated line and a line with a
stray `{count}` still in it.

## Versioning

- **Cosmetic** rewording (punctuation, capitalisation, a word that means the
  same thing): keep `semantic_version` unchanged and update the entry
  `version`. No translation goes stale.
- **Semantic** change — the meaning of a key changes, or a variable is added or
  removed: bump `semantic_version`. Packs built from an older source version are
  reported as stale by `ocf locale validate` until they record the new version.

## Fallback

Resolution walks the BCP-47 chain: `es-MX` → `es` → `en-US`.

- **UI text** may fall all the way to `en-US`. A missing label is not worth
  blocking a release.
- **Spoken narration** never falls back to `en-US` unless you pass the explicit
  override (`--no-strict`, `--allow-fallback`). A missing spoken line is a
  pre-render error, because the alternative is a translated session with an
  English sentence in the middle of it.

`es` in this repository is a deliberate **test fixture**: it is a machine draft
covering most but not all keys, so the strict check and the missing-key report
have something real to fail on. It is not an authoritative translation.

## Generated locales

`ocf locale pseudo --from en-US` builds an accented pseudo-locale. It is
generated in memory or written to a scratch directory and is never committed:
its job is to make untranslated strings and truncation problems obvious during
review.
