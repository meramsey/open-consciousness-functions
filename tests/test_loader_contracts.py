"""Isolated file discovery and I/O contracts against a synthetic resource tree."""

import hashlib
import json

import pytest
from ocf_tools import indexes, utils

pytestmark = pytest.mark.unit


@pytest.fixture
def tree(monkeypatch, tmp_path):
    paths = {
        "FUNCTIONS_DIR": "functions",
        "AUDIO_MANIFESTS_DIR": "audio/manifests",
        "AUDIO_IMPLEMENTATIONS_DIR": "audio/implementations",
        "AUDIO_SCRIPTS_DIR": "audio/scripts",
        "VOICES_PROFILES_DIR": "audio/voices/profiles",
    }
    monkeypatch.setattr(indexes, "REPO_ROOT", tmp_path)
    for name, relative in paths.items():
        monkeypatch.setattr(indexes, name, tmp_path / relative)
    return tmp_path


def put(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_function_discovery_sorting_identity_errors_and_lookups(tree):
    assert indexes.discover_function_files() == []
    assert indexes.load_all_functions() == []
    first = put(tree, "functions/nested/z.YAML", "id: OCF-COG-001\nslug: café\n")
    second = put(tree, "functions/a.yml", "id: OCF-COG-002\nslug: other\n")
    put(tree, "functions/ignore.txt", "ignored")
    (tree / "functions/directory.yaml").mkdir()
    assert indexes.discover_function_files() == sorted([first, second])
    assert [r.id for r in indexes.load_all_functions()] == ["OCF-COG-001", "OCF-COG-002"]
    assert indexes.load_function_by_id("OCF-COG-002").path == second
    assert indexes.load_function_by_slug_or_id("café").path == first
    assert indexes.load_function_by_slug_or_id("OCF-COG-001").path == first
    assert indexes.load_function_by_id("missing") is None
    assert indexes.load_function_by_slug_or_id("missing") is None
    put(tree, "functions/invalid.yaml", "slug: invalid\n")
    with pytest.raises(utils.OCFError, match="missing 'id' or 'slug'"):
        indexes.load_all_functions()


def test_yaml_mapping_banner_and_error_translation(tree):
    path = put(tree, "record.yaml", indexes.GENERATED_HEADER + "\n\nname: café\n")
    assert indexes.load_yaml_file(path) == {"name": "café"}
    for text, message in (("[broken", "Invalid YAML"), ("- not a mapping", "mapping at top level")):
        path.write_text(text)
        with pytest.raises(utils.OCFError, match=message):
            indexes.load_yaml_file(path)


def test_manifest_fallback_primary_precedence_and_directory_exclusion(tree):
    assert indexes.discover_audio_manifests() == []
    fallback = put(
        tree, "audio/implementations/fallback.yml", "id: OCF-AUDIO-9001\nfunction_id: OCF-COG-001\n"
    )
    assert indexes.discover_audio_manifests() == [fallback]
    (tree / "audio/manifests").mkdir()
    assert indexes.discover_audio_manifests() == [fallback]
    primary = put(
        tree, "audio/manifests/primary.yaml", "id: OCF-AUDIO-9002\nfunction_id: OCF-COG-002\n"
    )
    (tree / "audio/manifests/directory.yml").mkdir()
    assert indexes.discover_audio_manifests() == [primary]
    assert indexes.load_audio_manifests()[0]["id"] == "OCF-AUDIO-9002"
    assert indexes.find_audio_manifest("OCF-AUDIO-9002.yaml")["id"] == "OCF-AUDIO-9002"
    assert indexes.find_audio_manifest("OCF-AUDIO-9002")["id"] == "OCF-AUDIO-9002"
    assert indexes.find_audio_manifest("audio/manifests/primary.yaml")["id"] == "OCF-AUDIO-9002"
    assert indexes.find_audio_manifest(str(primary))["id"] == "OCF-AUDIO-9002"
    assert indexes.find_audio_manifest("no/file.yaml") is None
    assert indexes.audio_implementations_for("OCF-COG-002")
    assert indexes.audio_implementations_for("other") == []


@pytest.mark.parametrize(
    "discover,load,folder",
    [
        (
            indexes.discover_background_manifests,
            indexes.load_background_manifests,
            "audio/background/manifests",
        ),
        (indexes.discover_voice_profiles, indexes.load_voice_profiles, "audio/voices/profiles"),
        (indexes.discover_timed_transcripts, None, "audio/scripts"),
    ],
)
def test_resource_discovery_requires_files_and_handles_missing_trees(tree, discover, load, folder):
    assert discover() == []
    path = put(tree, folder + "/fixture.YML", "id: fixture\nusage: {functions: [OCF-COG-001]}\n")
    put(tree, folder + "/notes.txt", "ignored")
    (tree / folder / "directory.yaml").mkdir()
    assert discover() == [path]
    if load:
        assert load()[0]["id"] == "fixture"
    if folder.endswith("background/manifests"):
        assert indexes.background_presets_for("OCF-COG-001")[0]["id"] == "fixture"
        assert indexes.background_presets_for("unknown") == []


def test_proposals_and_unicode_json_are_deterministically_sorted(tree):
    assert indexes.count_proposals() == 0
    readme = put(tree, "proposals/README.md", "notes")
    proposal = put(tree, "proposals/draft/one.yaml", "id: OCFP-0001")
    put(tree, "proposals/ignored.txt", "ignored")
    (tree / "proposals/directory.md").mkdir()
    assert indexes.discover_proposal_files() == sorted([readme, proposal])
    assert indexes.count_proposals() == 1
    text = indexes.json_dump({"z": 2, "a": "café"})
    assert text.index('"a"') < text.index('"z"') and "café" in text and text.endswith("\n")
    assert json.loads(text) == {"a": "café", "z": 2}


def test_io_missing_encoding_directory_and_unicode_slug(tree):
    with pytest.raises(utils.OCFError, match="File not found"):
        utils.read_text(tree / "missing")
    with pytest.raises(utils.OCFError, match="Cannot read UTF-8"):
        utils.read_text(tree)
    bad = tree / "invalid-encoding"
    bad.write_bytes(b"\xff")
    with pytest.raises(utils.OCFError, match="Cannot read UTF-8"):
        utils.read_text(bad)
    assert utils.slugify("  Café / One\\Two: Three---Four! ") == "café-one-two-three-four"
    body = utils.generated_content("Unicode café")
    assert body.startswith(indexes.GENERATED_HEADER + "\n\n")
    assert utils.yaml_safe_load(utils.yaml_safe_dump({"text": "café"})) == {"text": "café"}


def test_atomic_write_collision_and_failure_keeps_old_bytes(tree, monkeypatch):
    path = put(tree, "record.txt", "old")
    with pytest.raises(utils.OCFFileExistsError):
        utils.write_text_atomic(path, "replacement", overwrite=False)
    original_unlink = utils.os.unlink

    def fail_replace(*args):
        raise OSError("replace failed")

    def cleanup_already_gone(path, *args, **kwargs):
        original_unlink(path)
        raise OSError("cleanup lost race")

    monkeypatch.setattr(utils.os, "replace", fail_replace)
    monkeypatch.setattr(utils.os, "unlink", cleanup_already_gone)
    with pytest.raises(OSError, match="replace failed"):
        utils.write_text_atomic(path, "new")
    assert path.read_text() == "old"
    assert list(tree.glob("*.tmp")) == []
    assert utils.sha256_of_file(path) == hashlib.sha256(b"old").hexdigest()


def test_authoring_date_is_iso_calendar_date(monkeypatch):
    import sys
    from datetime import date
    from types import SimpleNamespace

    class Calendar:
        @staticmethod
        def today():
            return date(2000, 2, 29)

    monkeypatch.setitem(sys.modules, "datetime", SimpleNamespace(date=Calendar))
    assert utils.current_date() == "2000-02-29"
