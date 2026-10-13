import pytest
from ocf_tools.artifact_names import ArtifactNamer, safe_component
from ocf_tools.utils import OCFError


def test_localized_name_and_optional_components_are_deterministic():
    namer = ArtifactNamer()
    assert namer.filename("OCF-BOD-010", "Nutricia", "en-us", "flac") == (
        "OCF-BOD-010 - Nutricia - en-US.flac"
    )
    assert (
        ArtifactNamer().filename(
            "OCF-BOD-010", "Nutricia", "en-US", ".mp3", variant="piper", version="1.2"
        )
        == "OCF-BOD-010 - Nutricia - en-US - piper - v1.2.mp3"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Café / 心", "Café-心"),
        ("CON", "_CON"),
        ("name. ", "name"),
        ("../../escape", "escape"),
    ],
)
def test_component_sanitizes_unicode_windows_names_and_path_separators(raw, expected):
    assert safe_component(raw) == expected


def test_duplicate_titles_are_case_insensitively_disambiguated():
    namer = ArtifactNamer()
    first = namer.filename("OCF-BOD-010", "Nutricia", "en-US", "mp3")
    second = namer.filename("OCF-BOD-010", "nutricia", "en-us", "mp3")
    assert first.casefold() != second.casefold()
    assert second.endswith("(2).mp3")


@pytest.mark.parametrize(
    ("function_id", "locale", "extension"),
    [
        ("../escape", "en-US", "mp3"),
        ("OCF-BOD-010", "bad_tag", "mp3"),
        ("OCF-BOD-010", "en-US", "exe"),
    ],
)
def test_rejects_invalid_identity_locale_and_extension(function_id, locale, extension):
    with pytest.raises(OCFError):
        ArtifactNamer().filename(function_id, "title", locale, extension)
