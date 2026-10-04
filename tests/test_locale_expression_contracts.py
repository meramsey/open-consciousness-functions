"""Deterministic ICU-subset and plural sandbox failures; no language assets or engines."""

import pytest
from ocf_tools import locale as l

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "expression,n,expected",
    [
        ("*", 1, True),
        ("n != 1", 2, True),
        ("n < 2", 1, True),
        ("n <= 2", 2, True),
        ("n > 2", 3, True),
        ("n >= 2", 2, True),
        ("-n == -2", 2, True),
        ("+n == 2", 2, True),
        ("n not in [1, 3]", 2, True),
        ("n in (2..4)", 3, True),
        ("n == 1 or n == 3", 2, False),
    ],
)
def test_supported_plural_rules_are_data_not_executable_python(expression, n, expected):
    assert l._eval_rule(expression, n) is expected
    assert l._in_spec(n, "2..4") is (2 <= n <= 4)


@pytest.mark.parametrize(
    "expression,match",
    [
        ("n in (4..2)", "inverted range"),
        ("n in (0..1001)", "too large"),
        ("n ==", "malformed plural rule"),
        ("x == 1", "may only reference n"),
        ("1 < n < 3", "chained comparisons"),
        ("n + 1 == 2", "unsupported construct"),
        ("n % 0 == 0", "invalid arithmetic"),
        ("n % 'bad' == 0", "invalid arithmetic"),
    ],
)
def test_malformed_and_unsafe_plural_rules_are_localization_errors(expression, match):
    with pytest.raises(l.LocalizationError, match=match):
        l._eval_rule(expression, 1)


@pytest.mark.parametrize("value", ["not a number", None, float("nan"), float("inf"), float("-inf")])
def test_nonfinite_counts_fail_consistently_before_formatting(value):
    for callback in (
        lambda: l.format_number(value),
        lambda: l.plural_category(value, "en"),
        lambda: l.format_message("{n, plural, other {# items}}", {"n": value}),
    ):
        with pytest.raises(l.LocalizationError, match="finite"):
            callback()


def test_fractional_custom_ordinal_and_exhausted_plural_tables():
    assert l.plural_category(1.5, "fr", {"many": "*"}) == "many"
    assert l.plural_category(1.5, "en", {}) == "other"
    assert l.plural_category(1, "en", {"one": "n == 2"}) == "other"
    assert l.plural_category(22, "en", ordinal=True) == "two"
    assert l.format_message("{count, plural, offset:1, other {#}}", {"count": 2}) == "1"


@pytest.mark.parametrize(
    "pattern,match",
    [
        ("words}", "unbalanced"),
        ("{bad name}", "invalid variable"),
        ("{name", "unterminated"),
        ("{name, number}", "unsupported argument"),
        ("{n, plural, other missing}", "malformed argument"),
        ("{n, plural, other {words}", "unterminated"),
        ("{n, plural, other {words", "unbalanced"),
        ("{n, plural, one {one}}", "other.*branch"),
    ],
)
def test_parser_reports_specific_syntax_errors(pattern, match):
    with pytest.raises(l.LocalizationError, match=match):
        l.parse_message(pattern)


def test_quotes_booleans_and_missing_variables_are_explicit():
    assert l.format_message("''") == "'"
    assert l.format_message("'{a''b}'") == "{a'b}"
    assert l.format_message("'{unterminated") == "{unterminated"
    assert l.format_message("{value}", {"value": True}) == "true"
    assert l.format_message("{value}", {"value": False}) == "false"
    for pattern in ("{value}", "{value, select, other {words}}"):
        with pytest.raises(l.LocalizationError, match="requires variable"):
            l.format_message(pattern, {})


def test_resource_variable_contracts_and_versions_are_reviewable():
    resource = l.NarrationResource(
        "fixture.key", "en-US", "narration", "{name}", variables=("unused",)
    )
    problems = resource.check_contract()
    assert any("undeclared" in p for p in problems) and any("never uses" in p for p in problems)
    with pytest.raises(l.LocalizationError, match="fixture.key"):
        resource.render({"unused": "value"})
    resource = l.NarrationResource(
        "fixture.key", "en-US", "narration", "{name}", variables=("name",)
    )
    for values in ({}, {"name": "Name", "extra": 1}):
        with pytest.raises(l.LocalizationError):
            resource.render(values)
    assert l._version_tuple("2.bad") == (2, 0, 0)
    assert l._version_tuple("1") == (1, 0, 0)
