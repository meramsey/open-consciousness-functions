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


@pytest.mark.unit
def test_media_and_sidecars_share_one_stem_even_at_length_limit():
    types = ["mp3", "flac", "wav", "txt", "lrc", "srt", "vtt", "timing.json"]
    names = ArtifactNamer(max_filename_length=80).filenames(
        "OCF-BOD-010",
        "Café title " * 20,
        "en-US",
        types,
        variant="narrator-" * 10,
        version="1234567890.1234567890.1234567890",
    )
    assert len({name[: -len(extension) - 1] for extension, name in names.items()}) == 1
    assert all(len(name) <= 80 for name in names.values())


@pytest.mark.unit
def test_group_disambiguates_collisions_in_any_extension():
    namer = ArtifactNamer()
    existing = namer.filename("OCF-BOD-010", "Nutricia", "en-US", "mp3")
    names = namer.filenames("OCF-BOD-010", "Nutricia", "en-US", ["flac", "mp3", "timing.json"])
    assert all("(2)." in name and name.casefold() != existing.casefold() for name in names.values())
    for invalid in ([], ["exe"]):
        with pytest.raises(OCFError, match="artifact group"):
            namer.filenames("OCF-BOD-010", "Nutricia", "en-US", invalid)


@pytest.mark.unit
def test_listener_names_include_title_voice_version_and_preparation_sorting():
    from ocf_tools.artifact_names import listener_export_names

    result = listener_export_names(
        "OCF-AUT-001",
        "Automatic Action",
        "en-US",
        ["flac", "mp3"],
        voice_label="Example — Original Voice",
        version="1.0.0",
    )
    assert (
        result["files"]["flac"]
        == "OCF-AUT-001 - Automatic-Action - en-US - Example-—-Original-Voice - v1.0.0.flac"
    )
    prep = listener_export_names(
        None,
        "Preparation Learning",
        "en-US",
        ["mp3"],
        voice_label="Example",
        version="0.1.0",
        session_kind="preparation-learning",
    )
    assert prep["directory"].startswith("00 - Preparation-Learning")
    assert prep["directory"] < result["directory"]
    assert prep["session_kind"] == "preparation-learning" and prep["sort_order"] == 0
    with pytest.raises(OCFError, match="must not have"):
        listener_export_names(
            "OCF-AUT-001",
            "Preparation Learning",
            "en-US",
            ["mp3"],
            voice_label="Example",
            version="1.0.0",
            session_kind="preparation-learning",
        )


@pytest.mark.unit
def test_listener_names_keep_identity_suffixes_and_require_declared_labels():
    from ocf_tools.artifact_names import listener_export_names

    result = listener_export_names(
        "OCF-AUT-001",
        "Long title " * 50,
        "en-US",
        ["flac", "timing.json"],
        voice_label="Narrator",
        version="12.34.56",
    )
    assert result["files"]["flac"].endswith(" - en-US - Narrator - v12.34.56.flac")
    assert all(len(name) <= 180 for name in result["files"].values())
    for voice, version in [("", "1.0.0"), ("Narrator", "")]:
        with pytest.raises(OCFError):
            listener_export_names(
                "OCF-AUT-001", "Title", "en-US", ["mp3"], voice_label=voice, version=version
            )


@pytest.mark.unit
def test_listener_names_fit_unicode_filesystem_components_without_losing_suffixes():
    from ocf_tools.artifact_names import listener_export_names

    result = listener_export_names(
        "OCF-AUT-001",
        "学習" * 80,
        "en-US",
        ["flac", "timing.json"],
        voice_label="Narrator",
        version="1.0.0",
    )
    assert all(len(name.encode("utf-8")) <= 240 for name in result["files"].values())
    assert result["files"]["flac"].endswith(" - Narrator - v1.0.0.flac")
