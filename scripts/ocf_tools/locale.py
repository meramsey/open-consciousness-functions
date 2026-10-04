"""Locale packs, BCP-47 normalization, and ICU-subset message formatting.

A locale pack is a directory of data files under ``locales/<locale>/``. Adding a
language is a data change: no application code is touched. A pack holds two
domains:

* ``ui`` -- operator- and player-facing labels. These may fall back to the
  canonical locale, because an untranslated label never reaches a listener.
* ``narration`` -- text spoken to the listener. These never fall back silently;
  see :meth:`LocaleCatalog.spoken`.

Semantic sessions reference narration by key (``narration_key``) and carry
``variables`` for the values, so the same session resolves to different narration
in every locale without editing the session.

Messages use the ICU MessageFormat subset documented in ``docs/LOCALIZATION.md``:
``{name}``, ``{name, plural, ...}``, ``{name, selectordinal, ...}``,
``{name, select, ...}``, ``#`` and ``offset:``. Runtime dependencies stay at
PyYAML + jsonschema; the syntax is ICU-compatible so a pack can move onto a full
ICU implementation later without rewriting its messages.
"""

from __future__ import annotations

import ast
import copy
import math
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from .indexes import load_yaml_file
from .paths import LOCALES_DIR
from .utils import OCFError

CANONICAL_LOCALE = "en-US"
"""Locale the repository authors in, and the last-resort fallback for UI strings."""

PSEUDO_LOCALE = "en-XA"
"""Generated pseudo-locale used to spot untranslated strings and layout bugs."""

PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")

UI_DOMAIN = "ui"
NARRATION_DOMAIN = "narration"

DEFAULT_PLURAL_RULES: dict[str, str] = {"one": "n == 1", "other": "*"}

# Compact CLDR plural rules for common language families, looked up by the
# language subtag (so pt-BR and pt-PT share `pt`). Languages that are not listed
# fall back to DEFAULT_PLURAL_RULES, which is correct for the large majority and
# never silently drops a plural form.
BUILTIN_PLURAL_RULES: dict[str, dict[str, str]] = {
    "en": {"one": "n == 1", "other": "*"},
    "de": {"one": "n == 1", "other": "*"},
    "nl": {"one": "n == 1", "other": "*"},
    "it": {"one": "n == 1", "other": "*"},
    "sv": {"one": "n == 1", "other": "*"},
    "da": {"one": "n in (1, 0..1)", "other": "*"},
    "pt": {"one": "n in (0, 1)", "other": "*"},
    "fr": {"one": "n in (0, 1)", "many": "n != 0 and n % 1000000 == 0", "other": "*"},
    "es": {"one": "n == 1", "many": "n != 0 and n % 1000000 == 0", "other": "*"},
    "ca": {"one": "n == 1", "other": "*"},
    "el": {"one": "n == 1", "other": "*"},
    "fi": {"one": "n == 1", "other": "*"},
    "tr": {"one": "n == 1", "other": "*"},
    "id": {"other": "*"},
    "vi": {"other": "*"},
    "ja": {"other": "*"},
    "ko": {"other": "*"},
    "zh": {"other": "*"},
    "th": {"other": "*"},
    "ru": {
        "one": "n % 10 == 1 and n % 100 != 11",
        "few": "n % 10 in (2, 3, 4) and not (n % 100 in (12, 13, 14))",
        "many": "n % 10 == 0 or n % 100 in (11, 12, 13, 14)",
        "other": "*",
    },
    "uk": {
        "one": "n % 10 == 1 and n % 100 != 11",
        "few": "n % 10 in (2, 3, 4) and not (n % 100 in (12, 13, 14))",
        "many": "n % 10 == 0 or n % 100 in (11, 12, 13, 14)",
        "other": "*",
    },
    "pl": {
        "one": "n == 1",
        "few": "n % 10 in (2, 3, 4) and not (n % 100 in (12, 13, 14))",
        "many": "not (n == 1) and n % 10 in (0, 1, 5, 6, 7, 8, 9) and not (n % 100 in (12, 13, 14))",
        "other": "*",
    },
    "cs": {"one": "n == 1", "few": "n in (2, 3, 4)", "many": "n != 1", "other": "*"},
    "sk": {"one": "n == 1", "few": "n in (2, 3, 4)", "many": "n != 1", "other": "*"},
    "ar": {
        "zero": "n == 0",
        "one": "n == 1",
        "two": "n == 2",
        "few": "n % 100 in (3..10, 103..110)",
        "many": "n % 100 in (11..99)",
        "other": "*",
    },
    "he": {"one": "n == 1", "two": "n == 2", "other": "*"},
    "hi": {"one": "n in (0, 1)", "other": "*"},
    "fa": {"one": "n in (0, 1)", "other": "*"},
}

# CLDR *ordinal* rules, used only by `selectordinal`. English is the language
# that actually needs them here; the others fall back to the cardinal table so
# an ordinal message still resolves somewhere sensible.
BUILTIN_ORDINAL_RULES: dict[str, dict[str, str]] = {
    "en": {
        "one": "n % 10 == 1 and n % 100 != 11",
        "two": "n % 10 == 2 and n % 100 != 12",
        "few": "n % 10 == 3 and n % 100 != 13",
        "other": "*",
    },
    "it": {"many": "*"},
    "fr": {"one": "n == 1", "other": "*"},
    "de": {"other": "*"},
    "es": {"other": "*"},
    "ja": {"other": "*"},
    "zh": {"other": "*"},
    "ko": {"other": "*"},
    "th": {"other": "*"},
    "ar": {"other": "*"},
    "ru": {"other": "*"},
}

# Languages whose message numbers use a decimal comma.
_DECIMAL_COMMA = {
    "es",
    "de",
    "fr",
    "it",
    "pt",
    "nl",
    "ru",
    "uk",
    "pl",
    "cs",
    "sk",
    "tr",
    "id",
    "vi",
    "da",
    "nb",
    "fi",
    "ro",
    "hu",
    "bg",
    "el",
    "ca",
    "hr",
    "sr",
    "lt",
    "lv",
    "et",
    "sl",
    "is",
}

_RTL_LANGUAGES = {"ar", "he", "fa", "ur", "ps", "yi", "dv", "ku", "sd"}

# Languages whose digit grouping is the Indian/crore system (12,34,567).
_INDIAN_GROUPING = {"hi", "bn", "gu", "kn", "ml", "mr", "pa", "ta", "te"}

# Thousands separator per language. Locales that group with a period or a space
# get it here so a formatted number inside a message reads correctly. The space
# is a plain space rather than CLDR's narrow no-break space: this runtime stays
# ASCII-safe and a pack cannot change digit grouping anyway.
_GROUPING_SEPARATOR = {
    "es": ".",
    "pt": ".",
    "de": ".",
    "it": ".",
    "nl": ".",
    "tr": ".",
    "da": ".",
    "ro": ".",
    "el": ".",
    "id": ".",
    "vi": ".",
    "hr": ".",
    "sr": ".",
    "ru": " ",
    "uk": " ",
    "pl": " ",
    "cs": " ",
    "sk": " ",
    "sv": " ",
    "nb": " ",
    "fi": " ",
    "fr": " ",
    "ca": " ",
    "hu": " ",
    "bg": " ",
    "lt": " ",
    "lv": " ",
    "et": " ",
    "is": " ",
}


_TAG_RE = re.compile(
    r"^(?P<language>[A-Za-z]{2,3})"
    r"(?:[-_](?P<script>[A-Za-z]{4}))?"
    r"(?:[-_](?P<region>[A-Za-z]{2}|[0-9]{3}))?$"
)

KEY_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z0-9-]+)+$")
VARIABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class LocalizationError(OCFError):
    """Malformed packs, missing keys, and variable-contract failures."""


# ---------------------------------------------------------------------------
# BCP-47 handling
# ---------------------------------------------------------------------------


def normalize_tag(tag: str | None) -> str | None:
    """Normalize a BCP-47 tag: ``en_us`` -> ``en-US``, ``ZH-hans-cn`` -> ``zh-Hans-CN``.

    Returns ``None`` for empty input and raises :class:`LocalizationError` for a
    malformed tag: an unsupported tag is reported, never guessed at.
    """
    if tag is None:
        return None
    raw = str(tag).strip()
    if not raw:
        return None
    match = _TAG_RE.match(raw)
    if not match:
        raise LocalizationError(
            f"not a well-formed BCP-47 language tag: {raw!r} "
            "(expected language[-script][-region], e.g. en-US, es, zh-Hans-CN)"
        )
    parts = [match.group("language").lower()]
    script = match.group("script")
    if script:
        parts.append(script[0].upper() + script[1:].lower())
    region = match.group("region")
    if region:
        parts.append(region.upper() if region.isalpha() else region)
    return "-".join(parts)


def locale_language(tag: str | None) -> str:
    """Return the primary language subtag of ``tag`` (``en`` for ``en-US``)."""
    return (normalize_tag(tag) or CANONICAL_LOCALE).split("-")[0]


def locale_direction(tag: str | None) -> str:
    """Return ``rtl`` for right-to-left languages, else ``ltr``."""
    return "rtl" if locale_language(tag) in _RTL_LANGUAGES else "ltr"


def fallback_chain(requested: str | None, *, default: str = CANONICAL_LOCALE) -> list[str]:
    """Locales consulted for ``requested``: ``es-MX, es, en-US``.

    Subtags drop off from the right, which is the practical approximation of the
    CLDR truncation algorithm. The canonical locale is always last, and only for
    UI text: spoken narration resolves in its own locale unless the caller opts
    out of strictness.
    """
    normalized = normalize_tag(requested) or default
    chain = [normalized]
    parts = normalized.split("-")
    for index in range(len(parts) - 1, 0, -1):
        candidate = "-".join(parts[:index])
        if candidate not in chain:
            chain.append(candidate)
    fallback = normalize_tag(default) or CANONICAL_LOCALE
    if fallback not in chain:
        chain.append(fallback)
    return chain


# ---------------------------------------------------------------------------
# Plural rules and number formatting
# ---------------------------------------------------------------------------

_ALLOWED_PLANE = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.BinOp,
    ast.Mod,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)


def _in_spec(value: float, spec: Any) -> bool:
    """Evaluate the ``2..4`` / ``7`` range syntax used by plural rules."""
    if isinstance(spec, (list, tuple)):
        return any(_in_spec(value, item) for item in spec)
    text = str(spec)
    if ".." in text:
        low_text, _, high_text = text.partition("..")
        return float(low_text) <= value <= float(high_text)
    return value == float(text)


_RANGE_RE = re.compile(r"(\d+)\.\.(\d+)")
_MAX_EXPANDED = 1000


def _expand_ranges(text: str) -> str:
    """Expand ``3..10`` into ``3,4,5,6,7,8,9,10`` so the rule parses as Python.

    CLDR rules are written with inclusive ranges; the sandboxed evaluator
    understands only plain literals and comparisons. Ranges must therefore sit
    inside a parenthesized ``in`` list, and are bounded so a malformed rule
    cannot expand into something enormous.
    """
    expanded = 0

    def replace(match: re.Match) -> str:
        nonlocal expanded
        low, high = int(match.group(1)), int(match.group(2))
        if high < low:
            raise LocalizationError(f"inverted range in plural rule: {match.group(0)}")
        expanded += high - low + 1
        if expanded > _MAX_EXPANDED:
            raise LocalizationError(f"plural rule range is too large: {match.group(0)}")
        return ", ".join(str(value) for value in range(low, high + 1))

    return _RANGE_RE.sub(replace, text)


def _eval_rule(expression: str, n: float) -> bool:
    """Evaluate one plural-rule condition against ``n`` in a sandbox."""
    text = expression.strip()
    if text == "*":
        return True
    text = _expand_ranges(text)
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise LocalizationError(f"malformed plural rule {expression!r}: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_PLANE):
            raise LocalizationError(f"unsupported construct in plural rule {expression!r}")

    def evaluate(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.BoolOp):
            values = [evaluate(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp):
            operand = evaluate(node.operand)
            if isinstance(node.op, ast.Not):
                return not operand
            return -operand if isinstance(node.op, ast.USub) else +operand
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Mod):
                return evaluate(node.left) % evaluate(node.right)
            raise LocalizationError(f"unsupported operator in plural rule {expression!r}")
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise LocalizationError(
                    f"chained comparisons are not supported in plural rules: {expression!r}"
                )
            operator = node.ops[0]
            left = evaluate(node.left)
            if isinstance(operator, (ast.In, ast.NotIn)):
                result = _in_spec(left, evaluate(node.comparators[0]))
                return not result if isinstance(operator, ast.NotIn) else result
            right = evaluate(node.comparators[0])
            if isinstance(operator, ast.Eq):
                return left == right
            if isinstance(operator, ast.NotEq):
                return left != right
            if isinstance(operator, ast.Lt):
                return left < right
            if isinstance(operator, ast.LtE):
                return left <= right
            if isinstance(operator, ast.Gt):
                return left > right
            return left >= right
        if isinstance(node, (ast.Tuple, ast.List)):
            return [evaluate(element) for element in node.elts]
        if isinstance(node, ast.Name):
            if node.id != "n":
                raise LocalizationError(f"plural rules may only reference n: {expression!r}")
            return n
        if isinstance(node, ast.Constant):
            return node.value
        raise LocalizationError(f"unsupported construct in plural rule {expression!r}")

    try:
        return bool(evaluate(tree))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise LocalizationError(f"invalid arithmetic in plural rule {expression!r}: {exc}") from exc


def _finite_number(value: Any) -> float:
    """Reject malformed/non-finite numeric message inputs with a locale error."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise LocalizationError(f"message number must be finite: {value!r}") from exc
    if not math.isfinite(number):
        raise LocalizationError(f"message number must be finite: {value!r}")
    return number


def plural_category(
    count: float | int,
    language: str,
    rules: Mapping[str, str] | None = None,
    *,
    ordinal: bool = False,
) -> str:
    """Return the CLDR plural category for ``count`` in ``language``.

    ``ordinal=True`` selects the ordinal table (``selectordinal``: 1st, 2nd,
    3rd, 4th) instead of the cardinal one used for counts.
    """
    if rules is not None:
        table = dict(rules)
    elif ordinal:
        language_key = locale_language(language)
        table = dict(
            BUILTIN_ORDINAL_RULES.get(
                language_key, BUILTIN_PLURAL_RULES.get(language_key, DEFAULT_PLURAL_RULES)
            )
        )
    else:
        table = dict(BUILTIN_PLURAL_RULES.get(locale_language(language), DEFAULT_PLURAL_RULES))
    absolute = abs(_finite_number(count))
    if absolute != int(absolute):
        # CLDR: a language that defines "many" uses it for fractional counts.
        return "many" if "many" in table else "other"
    for category in PLURAL_CATEGORIES:
        expression = table.get(category)
        if expression is None:
            continue
        if category == "other":
            return "other"
        if _eval_rule(expression, absolute):
            return category
    return "other"


def _group(digits: str, language: str) -> str:
    """Insert locale digit grouping into the integer part of a number."""
    if len(digits) <= 3 or digits.lstrip("-").startswith("0"):
        return digits
    language_key = locale_language(language)
    separator = _GROUPING_SEPARATOR.get(language_key, ",")
    sign = ""
    body = digits
    if body.startswith("-"):
        sign, body = "-", body[1:]
    if language_key in _INDIAN_GROUPING:
        # Indian grouping: the last three digits, then pairs (12,34,567).
        head, tail = body[:-3], body[-3:]
        size = 2
    else:
        head, tail = body[:-3], body[-3:]
        size = 3
    chunks: list[str] = []
    while len(head) > size:
        chunks.insert(0, head[-size:])
        head = head[:-size]
    if head:
        chunks.insert(0, head)
    chunks.append(tail)
    return sign + separator.join(chunks)


def format_number(value: float | int, language: str = CANONICAL_LOCALE) -> str:
    """Format a number for display inside a message.

    Integer values print without a decimal point; fractional values keep two
    decimals at most, use the locale's decimal separator, and gain the locale's
    digit grouping.
    """
    number = _finite_number(value)
    if number == int(number):
        return _group(str(int(number)), language)
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    integer, _, fraction = text.partition(".")
    separator = "," if locale_language(language) in _DECIMAL_COMMA else "."
    return f"{_group(integer, language)}{separator}{fraction}"


# ---------------------------------------------------------------------------
# ICU MessageFormat subset
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Literal:
    text: str


@dataclass(frozen=True)
class _Placeholder:
    name: str


@dataclass(frozen=True)
class _Pound:
    """``#``: the count minus the branch offset."""


@dataclass(frozen=True)
class _Choice:
    name: str
    kind: str
    offset: float
    options: Mapping[str, list[Any]]


# A runtime type alias, not an annotation, so `X | Y` is not an option here:
# this module also runs on Python 3.9.
_Part = Union[_Literal, _Placeholder, _Pound, _Choice]  # noqa: UP007


class _Parser:
    """Recursive-descent parser for the supported MessageFormat subset."""

    def __init__(self, pattern: str) -> None:
        self.text = pattern
        self.pos = 0

    def parse(self) -> list[_Part]:
        parts = self._parse_message(pound=False)
        if self.pos < len(self.text):
            raise LocalizationError(f"unbalanced '}}' in message: {self.text!r}")
        return parts

    def _parse_message(self, *, pound: bool) -> list[_Part]:
        parts: list[_Part] = []
        buffer: list[str] = []

        def flush() -> None:
            if buffer:
                parts.append(_Literal("".join(buffer)))
                buffer.clear()

        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "}":
                break
            if char == "\\" and self.text[self.pos + 1 : self.pos + 2] in ("#", "'", "\\"):
                # ICU lets a backslash escape a pound or quote so a literal
                # '#' can appear in a message without quoting the whole run.
                buffer.append(self.text[self.pos + 1])
                self.pos += 2
                continue
            if char == "'":
                self._parse_quote(buffer)
                continue
            if char == "{":
                flush()
                parts.append(self._parse_argument())
                continue
            if char == "#" and pound:
                flush()
                parts.append(_Pound())
                self.pos += 1
                continue
            buffer.append(char)
            self.pos += 1
        flush()
        return parts

    def _parse_quote(self, buffer: list[str]) -> None:
        """ICU apostrophe rules: ``''`` is a literal quote, ``'{'`` quotes."""
        if self.text[self.pos : self.pos + 2] == "''":
            buffer.append("'")
            self.pos += 2
            return
        if self.text[self.pos + 1 : self.pos + 2] in ("{", "}", "#"):
            self.pos += 1
            while self.pos < len(self.text):
                if self.text[self.pos] == "'":
                    if self.text[self.pos : self.pos + 2] == "''":
                        buffer.append("'")
                        self.pos += 2
                        continue
                    self.pos += 1
                    return
                buffer.append(self.text[self.pos])
                self.pos += 1
            return
        buffer.append("'")
        self.pos += 1

    def _parse_argument(self) -> _Part:
        self.pos += 1  # consume '{'
        name = self._read_until(",}").strip()
        if not VARIABLE_RE.match(name):
            raise LocalizationError(
                f"invalid variable name {name!r} in message (expected snake_case)"
            )
        if self.pos >= len(self.text):
            raise LocalizationError(f"unterminated argument in message: {self.text!r}")
        if self.text[self.pos] == "}":
            self.pos += 1
            return _Placeholder(name)
        self.pos += 1  # consume ','
        kind = self._read_until(",}").strip()
        if kind not in ("plural", "selectordinal", "select"):
            raise LocalizationError(
                f"unsupported argument type {kind!r} in message (expected plural, "
                "selectordinal, or select)"
            )
        self.pos += 1  # consume ','
        offset = 0.0
        if kind != "select":
            offset_match = re.match(r"\s*offset\s*:\s*(-?\d+(?:\.\d+)?)", self.text[self.pos :])
            if offset_match:
                offset = float(offset_match.group(1))
                self.pos += offset_match.end()
            if self.text[self.pos : self.pos + 1] == ",":
                self.pos += 1
        options = self._parse_options(pound=kind != "select")
        return _Choice(name, kind, offset, options)

    def _parse_options(self, *, pound: bool) -> dict[str, list[_Part]]:
        options: dict[str, list[_Part]] = {}
        while self.pos < len(self.text):
            self._skip_spaces()
            if self.pos >= len(self.text) or self.text[self.pos] == "}":
                break
            selector = self._read_until("{").strip()
            if not selector or self.text[self.pos : self.pos + 1] != "{":
                raise LocalizationError(f"malformed argument options in: {self.text!r}")
            self.pos += 1
            options[selector] = self._parse_message(pound=pound)
            if self.text[self.pos : self.pos + 1] != "}":
                raise LocalizationError(f"unbalanced '{{' in message: {self.text!r}")
            self.pos += 1
        if self.text[self.pos : self.pos + 1] != "}":
            raise LocalizationError(f"unterminated argument in message: {self.text!r}")
        self.pos += 1
        if "other" not in options:
            raise LocalizationError(f"argument requires an 'other' branch: {self.text!r}")
        return options

    def _read_until(self, stop: str) -> str:
        index = self.pos
        while index < len(self.text) and self.text[index] not in stop:
            index += 1
        value = self.text[self.pos : index]
        self.pos = index
        return value

    def _skip_spaces(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\n":
            self.pos += 1


def parse_message(pattern: str) -> list[_Part]:
    """Parse ``pattern`` into message parts."""
    return _Parser(pattern).parse()


def message_variables(pattern: str) -> set[str]:
    """Every variable a message refers to, including inside unselected branches."""
    found: set[str] = set()

    def walk(parts: Iterable[_Part]) -> None:
        for part in parts:
            if isinstance(part, _Placeholder):
                found.add(part.name)
            elif isinstance(part, _Choice):
                found.add(part.name)
                for branch in part.options.values():
                    walk(branch)

    walk(parse_message(pattern))
    return found


@dataclass(frozen=True)
class _Context:
    language: str
    plural_rules: Mapping[str, str] | None = None
    pound: float | None = None


def format_message(
    pattern: str,
    variables: Mapping[str, Any] | None = None,
    *,
    language: str = CANONICAL_LOCALE,
    plural_rules: Mapping[str, str] | None = None,
) -> str:
    """Format an ICU-subset ``pattern`` with ``variables``.

    Word order, punctuation, and inflection come from the message itself: the
    runtime selects whole branches and never concatenates sentence fragments.
    """
    return _render(
        parse_message(pattern),
        dict(variables or {}),
        _Context(language=normalize_tag(language) or language, plural_rules=plural_rules),
    )


def _render(parts: Sequence[_Part], values: Mapping[str, Any], ctx: _Context) -> str:
    out: list[str] = []
    for part in parts:
        if isinstance(part, _Literal):
            out.append(part.text)
        elif isinstance(part, _Pound):
            out.append(format_number(ctx.pound if ctx.pound is not None else 0, ctx.language))
        elif isinstance(part, _Placeholder):
            if part.name not in values:
                raise LocalizationError(f"message requires variable {part.name!r}")
            out.append(_stringify(values[part.name]))
        else:
            out.append(_render_choice(part, values, ctx))
    return "".join(out)


def _render_choice(choice: _Choice, values: Mapping[str, Any], ctx: _Context) -> str:
    if choice.name not in values:
        raise LocalizationError(f"message requires variable {choice.name!r}")
    value = values[choice.name]
    if choice.kind == "select":
        selector = _stringify(value)
        branch = choice.options.get(selector) or choice.options["other"]
        return _render(branch, values, ctx)
    count = _finite_number(value)
    selector = f"={int(count)}" if count == int(count) else format_number(count, ctx.language)
    branch = choice.options.get(selector)
    if branch is None:
        # CLDR applies plural rules to the value *after* the offset, so
        # `{n, plural, offset:1 ...}` with n=1 selects the branch for 0.
        shifted = count - choice.offset
        category = plural_category(
            shifted,
            ctx.language,
            ctx.plural_rules,
            ordinal=choice.kind == "selectordinal",
        )
        branch = choice.options.get(category) or choice.options["other"]
    inner = _Context(
        language=ctx.language, plural_rules=ctx.plural_rules, pound=count - choice.offset
    )
    return _render(branch, values, inner)


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return format_number(value, CANONICAL_LOCALE)
    return str(value)


# ---------------------------------------------------------------------------
# Pack model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NarrationResource:
    """One localized message plus its contract and translator metadata."""

    key: str
    locale: str
    domain: str
    text: str
    variables: tuple[str, ...] = ()
    status: str | None = None
    version: str | None = None
    pronunciation: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    timing: Mapping[str, Any] = field(default_factory=dict)
    notes: str | None = None
    file: str | None = None
    requires_events: tuple[str, ...] = ()
    required_pronunciation: tuple[str, ...] = ()

    @property
    def used_variables(self) -> set[str]:
        return message_variables(self.text)

    def check_contract(self) -> list[str]:
        """Declared variables must exactly match the ones the message uses."""
        problems: list[str] = []
        used = self.used_variables
        undeclared = sorted(used - set(self.variables))
        unused = sorted(set(self.variables) - used)
        if undeclared:
            problems.append(
                f"uses undeclared variable(s) {', '.join(undeclared)}; add them to `variables`"
            )
        if unused:
            problems.append(f"declares variable(s) {', '.join(unused)} that the message never uses")
        return problems

    def sample_variables(self) -> dict[str, Any]:
        """Plausible placeholder values for the declared variables.

        Used for previews (`ocf locale coverage`) and tests that need to prove a
        message renders without inventing real narration content.
        """
        samples: dict[str, Any] = {
            "count": 2,
            "n": 2,
            "index": 2,
            "minutes": 5,
            "seconds": 30,
            "reps": 3,
            "cycles": 3,
            "total": 10,
        }
        return {name: samples.get(name, name) for name in self.variables}

    def render(
        self,
        variables: Mapping[str, Any] | None = None,
        *,
        language: str | None = None,
        plural_rules: Mapping[str, str] | None = None,
    ) -> str:
        """Format this message, enforcing the declared variable contract."""
        problems = self.check_contract()
        if problems:
            raise LocalizationError(f"{self.locale}:{self.key} {'; '.join(problems)}")
        supplied = dict(variables or {})
        required = set(self.variables)
        missing = sorted(required - set(supplied))
        unknown = sorted(set(supplied) - required)
        if missing or unknown:
            parts = []
            if missing:
                parts.append(f"missing {', '.join(missing)}")
            if unknown:
                parts.append(f"unknown {', '.join(unknown)}")
            raise LocalizationError(
                f"{self.locale}:{self.key} variable mismatch: {'; '.join(parts)}"
            )
        return format_message(
            self.text,
            supplied,
            language=language or self.locale,
            plural_rules=plural_rules,
        )

    def hint_for(self, backend: str, token: str) -> str | None:
        """Pronunciation hint for ``token`` on ``backend``, if one exists."""
        hints = self.pronunciation.get(token) or {}
        return hints.get(backend) or None


class LocalePack:
    """One locale's resources plus its provenance manifest."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        entries: Mapping[str, NarrationResource],
        path: Path | None = None,
    ) -> None:
        self.manifest = dict(manifest)
        self.entries: dict[str, NarrationResource] = dict(entries)
        self.path = path

    @property
    def locale(self) -> str:
        return str(self.manifest.get("locale", CANONICAL_LOCALE))

    @property
    def status(self) -> str:
        return str(self.manifest.get("status", "draft"))

    @property
    def direction(self) -> str:
        return str(self.manifest.get("direction") or locale_direction(self.locale))

    @property
    def semantic_version(self) -> str:
        return str(self.manifest.get("semantic_version", "0.0.0"))

    @property
    def translation(self) -> Mapping[str, Any]:
        return dict(self.manifest.get("translation") or {})

    @property
    def is_canonical(self) -> bool:
        return self.status == "canonical"

    def keys(self, domain: str | None = None) -> list[str]:
        return sorted(
            key for key, entry in self.entries.items() if domain is None or entry.domain == domain
        )

    def domains(self) -> set[str]:
        return {entry.domain for entry in self.entries.values()}

    def get(self, key: str) -> NarrationResource | None:
        return self.entries.get(key)

    def by_domain(self, domain: str) -> dict[str, NarrationResource]:
        return {key: entry for key, entry in self.entries.items() if entry.domain == domain}

    def plural_rules(self) -> Mapping[str, str] | None:
        rules = self.manifest.get("plural_rules")
        return dict(rules) if isinstance(rules, dict) else None

    def describe(self) -> str:
        narration = len(self.by_domain(NARRATION_DOMAIN))
        translation = self.translation
        if self.is_canonical:
            return (
                f"{self.locale:<7} {self.status:<9} v{self.semantic_version:<7} "
                f"{len(self.entries)} keys ({narration} narration)"
            )
        return (
            f"{self.locale:<7} {self.status:<9} v{self.semantic_version:<7} "
            f"{len(self.entries)} keys ({narration} narration)  "
            f"from {translation.get('source_locale', '?')}"
            f"@{translation.get('source_semantic_version', '?')}"
        )


def _entry_from_value(
    key: str, value: Any, locale: str, domain: str, filename: str
) -> NarrationResource:
    if isinstance(value, str):
        return NarrationResource(key=key, locale=locale, domain=domain, text=value, file=filename)
    if not isinstance(value, dict):
        raise LocalizationError(f"{locale} {filename}: entry {key!r} must be a string or object")
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        raise LocalizationError(f"{locale} {filename}: entry {key!r} needs non-empty `text`")
    variables = tuple(value.get("variables") or ())
    for name in variables:
        if not isinstance(name, str) or not VARIABLE_RE.match(name):
            raise LocalizationError(
                f"{locale} {filename}: entry {key!r} declares invalid variable {name!r}"
            )
    return NarrationResource(
        key=key,
        locale=locale,
        domain=domain,
        text=text,
        variables=variables,
        status=value.get("status"),
        version=value.get("version"),
        pronunciation=dict(value.get("pronunciation") or {}),
        timing=dict(value.get("timing") or {}),
        notes=value.get("notes"),
        file=filename,
        requires_events=tuple(value.get("requires_events") or ()),
        required_pronunciation=tuple(value.get("required_pronunciation") or ()),
    )


def load_pack(path: Path) -> LocalePack:
    """Load one locale pack directory (manifest plus declared resource files)."""
    manifest_path = path / "manifest.yaml"
    if not manifest_path.is_file():
        raise LocalizationError(f"locale pack {path} has no manifest.yaml")
    manifest = load_yaml_file(manifest_path)
    if not isinstance(manifest, dict):
        raise LocalizationError(f"locale pack {path}: manifest.yaml must be a mapping")
    locale = normalize_tag(manifest.get("locale"))
    if locale is None:
        raise LocalizationError(f"locale pack {path}: manifest declares no `locale`")
    entries: dict[str, NarrationResource] = {}
    for resource in manifest.get("resources") or []:
        filename = str(resource.get("file", ""))
        declared_domain = str(resource.get("domain", UI_DOMAIN))
        resource_path = path / filename
        if not resource_path.is_file():
            raise LocalizationError(
                f"{locale} pack {path.name}: manifest declares resource {filename!r} "
                "but the file is missing"
            )
        data = load_yaml_file(resource_path)
        if not isinstance(data, dict):
            raise LocalizationError(f"{locale} {filename}: resource file must be a mapping")
        file_domain = str(data.get("domain", declared_domain))
        if file_domain != declared_domain:
            raise LocalizationError(
                f"{locale} {filename}: domain {file_domain!r} does not match manifest "
                f"domain {declared_domain!r}"
            )
        if normalize_tag(data.get("locale")) != locale:
            raise LocalizationError(
                f"{locale} {filename}: resource locale {data.get('locale')!r} does not match "
                f"pack locale {locale!r}"
            )
        for key, value in (data.get("entries") or {}).items():
            if not KEY_RE.match(str(key)):
                raise LocalizationError(
                    f"{locale} {filename}: invalid key {key!r} (expected a lowercase dotted "
                    "namespace, e.g. focus.eleven.instruction)"
                )
            if str(key) in entries:
                raise LocalizationError(f"{locale}: duplicate key {str(key)!r} in {filename}")
            entries[str(key)] = _entry_from_value(str(key), value, locale, file_domain, filename)
    return LocalePack(manifest, entries, path)


@dataclass(frozen=True)
class Resolution:
    """Which pack answered a key, and whether the fallback chain was walked."""

    key: str
    locale: str
    origin_locale: str
    domain: str
    fallback: bool


class LocaleCatalog:
    """Registry of every pack under ``locales/``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else LOCALES_DIR
        self.packs: dict[str, LocalePack] = {}
        self.problems: list[str] = []
        if not self.root.is_dir():
            return
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or directory.name.startswith((".", "_")):
                continue
            try:
                pack = load_pack(directory)
            except LocalizationError as exc:
                self.problems.append(str(exc))
                continue
            normalized = normalize_tag(directory.name)
            if normalized != pack.locale:
                self.problems.append(
                    f"pack directory {directory.name!r} does not match declared locale "
                    f"{pack.locale!r}"
                )
                continue
            if normalized in self.packs:
                self.problems.append(f"duplicate locale pack: {normalized}")
                continue
            self.packs[normalized] = pack

    # -- lookups ----------------------------------------------------------

    @property
    def canonical_locale(self) -> str:
        for locale, pack in sorted(self.packs.items()):
            if pack.is_canonical:
                return locale
        return CANONICAL_LOCALE

    @property
    def canonical(self) -> LocalePack | None:
        return self.packs.get(self.canonical_locale)

    def locales(self) -> list[str]:
        return sorted(self.packs)

    def get(self, locale: str | None) -> LocalePack | None:
        normalized = normalize_tag(locale)
        return self.packs.get(normalized) if normalized else None

    def require(self, locale: str | None) -> LocalePack:
        pack = self.get(locale)
        if pack is None:
            known = ", ".join(self.locales()) or "none"
            raise LocalizationError(
                f"no locale pack for {normalize_tag(locale) or locale!r} (available: {known})"
            )
        return pack

    def chain(self, requested: str | None, *, default: str = CANONICAL_LOCALE) -> list[str]:
        """Installed locales consulted for ``requested``, canonical last."""
        fallback = normalize_tag(default) or CANONICAL_LOCALE
        return [
            locale for locale in fallback_chain(requested, default=fallback) if locale in self.packs
        ]

    def spoken_chain(self, requested: str | None) -> list[str]:
        """Locales that may supply *spoken* text for ``requested``.

        Regional tags are served by their installed parent (``es-MX`` -> ``es``),
        because a language variant is the same language to a listener. The
        canonical locale is excluded unless it was the locale asked for: silently
        reading English inside a translated session is exactly what the strict
        spoken rule exists to prevent.
        """
        normalized = normalize_tag(requested) or self.canonical_locale
        parents = [
            locale
            for locale in self.chain(normalized)
            if locale_language(locale) == locale_language(normalized)
        ]
        if not parents:
            raise LocalizationError(
                f"no locale pack for spoken narration in {normalized!r} "
                f"(available: {', '.join(self.locales()) or 'none'}); install a pack for "
                f"{normalized!r} or an installed parent locale, or re-run with the "
                "explicit fallback override to allow "
                f"{self.canonical_locale}"
            )
        return parents

    def plural_rules_for(self, locale: str | None) -> Mapping[str, str] | None:
        pack = self.get(locale)
        return pack.plural_rules() if pack else None

    # -- resolution -------------------------------------------------------

    def lookup(
        self,
        key: str,
        locale: str | None,
        *,
        domain: str | None = None,
        fallback: bool = True,
    ) -> Resolution:
        """Find ``key`` for ``locale``, optionally walking the fallback chain."""
        normalized = normalize_tag(locale) or self.canonical_locale
        consulted = self.chain(normalized) if fallback else self.spoken_chain(normalized)
        for candidate in consulted:
            pack = self.packs.get(candidate)
            if pack is None:
                continue
            entry = pack.get(key)
            if entry is None or (domain is not None and entry.domain != domain):
                continue
            return Resolution(
                key=key,
                locale=normalized,
                origin_locale=candidate,
                domain=entry.domain,
                fallback=candidate != normalized,
            )
        raise LocalizationError(
            f"missing {'spoken narration' if domain == NARRATION_DOMAIN else 'resource'} {key!r} "
            f"for locale {normalized!r}; consulted {' > '.join(consulted)}"
        )

    def text(
        self,
        key: str,
        locale: str | None = None,
        variables: Mapping[str, Any] | None = None,
        *,
        fallback: bool = True,
    ) -> str:
        """Resolve a UI string, falling back to the canonical locale by default."""
        resolution = self.lookup(key, locale, domain=UI_DOMAIN, fallback=fallback)
        entry = self.require(resolution.origin_locale).entries[key]
        return entry.render(variables, plural_rules=self.plural_rules_for(resolution.origin_locale))

    def spoken(
        self,
        key: str,
        locale: str | None = None,
        variables: Mapping[str, Any] | None = None,
        *,
        strict: bool = True,
    ) -> str:
        """Resolve listener narration.

        Strict (the default, and what rendering uses): the key must exist in the
        requested locale. A missing translation is an error to fix, not a reason
        to drop an English sentence into a translated session.
        """
        resolution = self.lookup(key, locale, domain=NARRATION_DOMAIN, fallback=not strict)
        pack = self.require(resolution.origin_locale)
        return pack.entries[key].render(
            variables, plural_rules=self.plural_rules_for(resolution.origin_locale)
        )

    def resource(
        self,
        key: str,
        locale: str | None = None,
        *,
        domain: str | None = None,
        fallback: bool = True,
    ) -> tuple[NarrationResource, Resolution]:
        resolution = self.lookup(key, locale, domain=domain, fallback=fallback)
        return self.require(resolution.origin_locale).entries[key], resolution

    def provenance(self) -> dict[str, Any]:
        """Per-pack translation provenance, for `ocf locale list`."""
        return {
            locale: {
                "status": pack.status,
                "direction": pack.direction,
                "semantic_version": pack.semantic_version,
                "keys": len(pack.entries),
                "narration_keys": len(pack.by_domain(NARRATION_DOMAIN)),
                "translation": dict(pack.translation),
            }
            for locale, pack in sorted(self.packs.items())
        }

    # -- coverage ---------------------------------------------------------

    def _keys_of(self, pack: LocalePack | None, domain: str | None) -> list[str]:
        return [] if pack is None else pack.keys(domain)

    def missing_keys(self, locale: str, *, domain: str | None = None) -> list[str]:
        """Canonical keys absent from ``locale``."""
        canonical, target = self.canonical, self.require(locale)
        if canonical is None:
            return []
        return [key for key in self._keys_of(canonical, domain) if target.get(key) is None]

    def unknown_keys(self, locale: str) -> list[str]:
        """Keys in ``locale`` that the canonical pack does not define."""
        canonical, target = self.canonical, self.require(locale)
        if canonical is None:
            return []
        return [key for key in target.keys() if canonical.get(key) is None]

    def stale_translations(self, locale: str) -> bool:
        """True when a derived pack was built against an older canonical version."""
        canonical, pack = self.canonical, self.get(locale)
        if canonical is None or pack is None or pack.is_canonical:
            return False
        recorded = str(pack.translation.get("source_semantic_version") or "")
        if not recorded:
            return True
        return _version_tuple(recorded)[0] < _version_tuple(canonical.semantic_version)[0]

    def stale_keys(self, locale: str) -> list[str]:
        """Keys whose canonical entry version is newer than the translation's."""
        canonical, pack = self.canonical, self.get(locale)
        if canonical is None or pack is None or pack.is_canonical:
            return []
        stale: list[str] = []
        for key, entry in pack.entries.items():
            source = canonical.get(key)
            if source is None:
                continue
            source_version = str(source.version or canonical.semantic_version)
            if (
                entry.version
                and _version_tuple(entry.version)[0] < _version_tuple(source_version)[0]
            ):
                stale.append(key)
        return sorted(stale)

    def coverage(self, locale: str, *, domain: str | None = None) -> dict[str, Any]:
        canonical, pack = self.canonical, self.require(locale)
        total = len(self._keys_of(canonical, domain))
        covered = sum(1 for key in self._keys_of(canonical, domain) if pack.get(key))
        return {
            "total": total,
            "covered": covered,
            "percent": round(100.0 * covered / total, 1) if total else 100.0,
        }


def _version_tuple(value: str) -> tuple[int, int, int]:
    numbers: list[int] = []
    for part in str(value).split(".")[:3]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


# ---------------------------------------------------------------------------
# Pseudo-locale
# ---------------------------------------------------------------------------

_PSEUDO_ACCENTS = {
    "a": "á",
    "e": "é",
    "i": "í",
    "o": "ö",
    "u": "ú",
    "y": "ý",
    "c": "ç",
    "n": "ñ",
    "s": "š",
    "z": "ž",
    "A": "Á",
    "E": "É",
    "I": "Í",
    "O": "Ö",
    "U": "Ú",
    "Y": "Ý",
    "C": "Ç",
    "N": "Ñ",
    "S": "Š",
    "Z": "Ž",
}


def _pseudo_text(text: str) -> str:
    """Accent ASCII letters so untranslated strings and padding problems show.

    ICU argument syntax is left untouched: the derived pack must stay renderable,
    otherwise a pseudo-locale run would fail before it could report anything.
    """
    out: list[str] = []
    depth = 0
    for char in text:
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        out.append(char if depth else _PSEUDO_ACCENTS.get(char, char))
    return "".join(out)


def build_pseudo_pack(
    catalog: LocaleCatalog,
    source_locale: str | None = None,
    *,
    locale: str = PSEUDO_LOCALE,
) -> LocalePack:
    """Derive a pseudo-locale pack from its source locale.

    Generated in memory and never committed: it exists to make untranslated
    strings, truncation, and layout problems obvious during review.
    """
    source = catalog.require(source_locale or catalog.canonical_locale)
    entries = {
        key: NarrationResource(
            key=key,
            locale=locale,
            domain=entry.domain,
            text=_pseudo_text(entry.text),
            variables=entry.variables,
            status="machine",
            version=source.semantic_version,
            pronunciation=entry.pronunciation,
            timing=entry.timing,
            notes=f"pseudo-locale derived from {source.locale}@{source.semantic_version}",
            file=entry.file,
            requires_events=entry.requires_events,
            required_pronunciation=entry.required_pronunciation,
        )
        for key, entry in source.entries.items()
    }
    manifest = {
        "schema_version": "1.0",
        "locale": locale,
        "language_name": "English (pseudo-locale)",
        "direction": "ltr",
        "status": "machine",
        "semantic_version": source.semantic_version,
        "translation": {
            "source_locale": source.locale,
            "source_semantic_version": source.semantic_version,
            "translation_version": source.semantic_version,
            "translator": "generated",
            "notes": "generated by `ocf locale pseudo`; never commit",
        },
        "resources": [
            {
                "file": resource.get("file"),
                "domain": resource.get("domain", UI_DOMAIN),
                "description": f"Pseudo-locale copy of {source.locale} {resource.get('file')}",
            }
            for resource in source.manifest.get("resources") or []
        ],
        "notes": "Generated pseudo-locale; accents expose untranslated strings.",
    }
    if source.plural_rules():
        # Pseudo text has the source's shape, so it keeps the source grammar.
        manifest["plural_rules"] = dict(source.plural_rules())
    return LocalePack(manifest, entries, None)


# ---------------------------------------------------------------------------
# Document resolution
# ---------------------------------------------------------------------------


def document_locale(doc: Mapping[str, Any]) -> str:
    """Locale a timed document targets, defaulting to the canonical locale."""
    return normalize_tag(doc.get("locale")) or CANONICAL_LOCALE


def iter_events(doc: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every timeline event dict in a document (flat or sectioned)."""
    for event in doc.get("timeline") or []:
        if isinstance(event, dict):
            yield event
    for section in doc.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for event in section.get("timeline") or []:
            if isinstance(event, dict):
                yield event


@dataclass
class ResolutionReport:
    """What a document resolution did, for provenance and assertions."""

    locale: str = CANONICAL_LOCALE
    keys: list[str] = field(default_factory=list)
    inline_events: int = 0
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "locale": self.locale,
            "keys": list(self.keys),
            "inline_events": self.inline_events,
            "issues": list(self.issues),
        }


def resolve_document(
    doc: Mapping[str, Any],
    locale: str | None = None,
    *,
    catalog: LocaleCatalog | None = None,
    strict: bool = True,
    report: ResolutionReport | None = None,
) -> dict[str, Any]:
    """Resolve a document's ``narration_key`` events into ``text``.

    The resolved document keeps every ``narration_key`` plus a ``narration``
    provenance block, so the spoken line stays traceable back to its resource.
    Inline ``text`` is left alone for backward compatibility. Strict mode raises
    on the first batch of missing spoken resources, which is what makes a
    pre-render check fail loudly instead of emitting a mixed-language session.
    """
    catalog = catalog or LocaleCatalog()
    target = normalize_tag(locale) or document_locale(doc)
    # A regional tag may be served by an installed parent pack, so consult the
    # chain the same way ``lookup`` will instead of requiring the exact tag.
    pack = catalog.get(target)
    if pack is None:
        serving = (
            catalog.spoken_chain(target)
            if strict
            else (catalog.chain(target) or catalog.spoken_chain(target))
        )
        pack = catalog.require(serving[0])
    resolved = copy.deepcopy(dict(doc))
    resolved["locale"] = target
    issues: list[str] = []
    keys: list[str] = []
    inline_events = 0
    provenance: list[dict[str, Any]] = []
    previous_origins = {
        item.get("id"): item.get("locale")
        for item in (doc.get("narration") or {}).get("resolved", [])
    }

    for event in iter_events(resolved):
        key = event.get("narration_key")
        if not key:
            if not event.get("text"):
                continue
            inline_events += 1
            origin = (
                event.get("locale") or previous_origins.get(event.get("id")) or document_locale(doc)
            )
            if locale_language(origin) != locale_language(target) and strict:
                issues.append(
                    f"inline event {event.get('id', '?')} is authored in {origin}, "
                    f"not {target}; explicitly allow fallback to retain this wording"
                )
            provenance.append({"id": event.get("id"), "key": "inline", "locale": origin})
            continue
        try:
            entry, resolution = catalog.resource(
                str(key), target, domain=NARRATION_DOMAIN, fallback=not strict
            )
            text = entry.render(
                event.get("variables") or {},
                plural_rules=catalog.plural_rules_for(resolution.origin_locale),
            )
        except LocalizationError as exc:
            issues.append(f"event {event.get('id', '?')}: {exc}")
            continue
        event["text"] = text
        keys.append(str(key))
        provenance.append(
            {
                "id": event.get("id"),
                "key": str(key),
                "locale": resolution.origin_locale,
                "resource_file": entry.file,
                "version": entry.version,
                "status": entry.status or (catalog.get(resolution.origin_locale) or pack).status,
            }
        )

    if issues:
        if strict:
            raise LocalizationError(
                f"required spoken narration is missing for {target}: {'; '.join(issues)}"
            )
        if report is not None:
            report.issues.extend(issues)

    resolved["narration"] = {
        "locale": target,
        "direction": locale_direction(target),
        "strict": bool(strict),
        "keys": keys,
        "inline_events": inline_events,
        "resolved": provenance,
    }
    if report is not None:
        report.locale = target
        report.keys = keys
        report.inline_events = inline_events
    return resolved


def document_key_usage(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Count keyed vs inline narration in a document."""
    keyed: list[str] = []
    inline = 0
    both = 0
    for event in iter_events(doc):
        key = event.get("narration_key")
        if key:
            keyed.append(str(key))
            if event.get("text"):
                both += 1
        else:
            inline += 1
    return {"keys": keyed, "keyed": len(keyed), "inline": inline, "both": both}


def missing_narration_keys(
    doc: Mapping[str, Any], locale: str, catalog: LocaleCatalog | None = None
) -> list[str]:
    """Keys the document requires that ``locale`` does not provide."""
    catalog = catalog or LocaleCatalog()
    missing = set()
    for key in document_key_usage(doc)["keys"]:
        try:
            catalog.lookup(key, locale, domain=NARRATION_DOMAIN, fallback=False)
        except LocalizationError:
            missing.add(key)
    return sorted(missing)
