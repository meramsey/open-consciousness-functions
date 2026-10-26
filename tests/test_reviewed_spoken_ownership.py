"""Reviewed speech is an explicit realization of one identity, not a free alias."""

from pathlib import Path

import pytest
from ocf_tools.validators import validate_narration_usage

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "owner,spoken,valid",
    [
        ("OCF-SLP-005", "Plus Sleep Easy", True),
        ("OCF-SLP-005", "Plus Quiet Sleep", False),
        ("OCF-EXP-001", "Plus Sleep Easy", False),
        ("OCF-BOD-006", "Plus Heart Flow", True),
        ("OCF-BOD-006", "Plus Heart Better", False),
        ("OCF-BOD-006", "Plus Heart Better Better", False),
    ],
)
def test_complete_spoken_value_must_be_declared_and_belong_to_owner(owner, spoken, valid):
    document = {
        "locale": "en-US",
        "function_id": owner,
        "timeline": [
            {
                "id": "explain",
                "at": 0,
                "narration_key": "function.activation.command",
                "variables": {"command": spoken},
            }
        ],
    }
    result = validate_narration_usage(document, Path("fixture.yaml"))
    assert result.ok is valid
    if not valid:
        assert any(
            issue.code in {"narration-command-invalid", "narration-command-owner"}
            for issue in result.errors
        )
