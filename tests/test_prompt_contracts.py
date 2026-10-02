"""Interactive controls are isolated with synthetic input, never user review or file edits."""

import pytest
from ocf_tools.prompts import (
    BACK,
    QUIT,
    SKIP_CONST,
    WizardQuit,
    ask,
    ask_pick,
    ask_yes_no,
    multi_ask,
)


def feed(monkeypatch, values):
    values = iter(values)
    monkeypatch.setattr("builtins.input", lambda prompt: next(values))


@pytest.mark.unit
@pytest.mark.parametrize(
    "answer,intent,value",
    [
        ("back", "back", BACK),
        ("skip", "skip", SKIP_CONST),
        ("quit", "quit", QUIT),
        ("", "value", "fallback"),
    ],
)
def test_controls_and_default_preserve_intent(monkeypatch, answer, intent, value):
    feed(monkeypatch, [answer])
    result = ask("fixture", default="fallback")
    assert (result.intent, result.value) == (intent, value)


@pytest.mark.unit
def test_help_validation_choices_and_disallowed_controls(monkeypatch, capsys):
    feed(monkeypatch, ["?", "bad", "good"])
    assert (
        ask(
            "fixture",
            help_text="fixture help",
            validator=lambda v: None if v == "good" else "invalid fixture",
        ).value
        == "good"
    )
    assert "fixture help" in capsys.readouterr().out
    feed(monkeypatch, ["?", "0", "2"])
    assert ask_pick("choose", ["One", "Two"]).value == "Two"
    feed(monkeypatch, ["YES"])
    assert ask_yes_no("confirm").value == "yes"
    feed(monkeypatch, ["back"])
    assert ask("literal", allow_back=False, allow_skip=False).value == "back"


@pytest.mark.unit
@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_interrupted_input_quits_cleanly(monkeypatch, exception):
    def interrupted(prompt):
        raise exception()

    monkeypatch.setattr("builtins.input", interrupted)
    assert ask("fixture").intent == "quit"


@pytest.mark.unit
def test_multi_value_empty_policy_and_quit_are_respected(monkeypatch):
    feed(monkeypatch, [""])
    assert multi_ask("optional", allow_empty=True) == []
    feed(monkeypatch, ["", "a, b,, c"])
    assert multi_ask("required", allow_empty=False) == ["a", "b", "c"]
    feed(monkeypatch, ["skip"])
    assert multi_ask("fixture") == []
    feed(monkeypatch, ["quit"])
    with pytest.raises(WizardQuit):
        multi_ask("fixture")
