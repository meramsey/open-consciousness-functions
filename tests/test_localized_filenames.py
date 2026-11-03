"""L4 planning reuses artifact-name safety without changing lookup identity."""

import pytest
from ocf_tools.localized_filenames import collision_key, filename_plan, readable_filename
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_stable_id_prefix_and_nfc_unicode_suffix_are_deterministic():
    assert readable_filename("OCF-EMO-003", "Empathize") == "OCF-EMO-003-Empathize.yaml"
    assert readable_filename("OCF-EMO-003", "Cafe\u0301") == readable_filename(
        "OCF-EMO-003", "Café"
    )
    assert collision_key("OCF-EMO-003-Café.yaml") == collision_key("ocf-emo-003-CAFE\u0301.YAML")


@pytest.mark.unit
@pytest.mark.parametrize("text", ["CON", "A/B:C*?", "世界" * 100, "🦄" * 100])
def test_windows_characters_reserved_names_and_utf8_length_are_bounded(text):
    result = readable_filename("OCF-EMO-003", text)
    assert result.startswith("OCF-EMO-003-") and result.endswith(".yaml")
    assert len(result.encode("utf-8")) <= 145
    assert not any(char in result for char in '<>:"/\\|?*')
    assert not result.endswith((".", " "))


@pytest.mark.unit
@pytest.mark.parametrize("identity,text", [("../escape", "Title"), ("OCF-EMO-003", " ... ")])
def test_invalid_identity_and_empty_title_fail_closed(identity, text):
    with pytest.raises(OCFError):
        readable_filename(identity, text)


@pytest.mark.integration
def test_complete_catalog_plan_does_not_overwrite_unlisted_historical_pilot():
    report = filename_plan()
    assert report["count"] == 58
    assert len({row["function_id"] for row in report["mapping"]}) == 58
    assert all(
        row["new_path"].split("/")[-1].startswith(row["function_id"] + "-")
        for row in report["mapping"]
    )
    assert report["blockers"] == []
    assert any(
        row["function_id"] == "OCF-EMO-003"
        for row in report["verified_historical_destination_reuse"]
    )
    assert filename_plan(locale="es")["count"] == 0  # Partial locale, not invented translations.
