"""Regression checks for frozen HPlus spoken wording and its integrity tool."""

import pytest
from tools.check_hplus_narration_integrity import check, differences

pytestmark = pytest.mark.integration


def test_all_function_and_shared_narration_text_matches_frozen_baseline():
    assert check() == []


@pytest.mark.unit
def test_integrity_comparison_reports_missing_extra_and_changed_keys():
    assert differences(
        {"old.yaml::spoken.old": "old-hash", "same.yaml::spoken.same": "same-hash"},
        {"new.yaml::spoken.new": "new-hash", "same.yaml::spoken.same": "different-hash"},
    ) == [
        "missing key: old.yaml::spoken.old",
        "unexpected key: new.yaml::spoken.new",
        "text changed: same.yaml::spoken.same",
    ]
