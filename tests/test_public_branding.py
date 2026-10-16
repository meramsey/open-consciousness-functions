"""Imported artwork presentation and independent new-cover defaults."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from ocf_tools import agent_api, artwork, release
from ocf_tools.utils import OCFError, sha256_of_file
from tools import brand_presentation as presentation


def test_tracked_presentation_sources_hashes_readme_images_and_badges():
    data = presentation.check_assets()
    readme = presentation.check_readme()
    assert data["brand_version"] == "0.3.0" and data["human_approval"] is None
    assert readme["workflow_badges"] == ["generated-index-check", "lint", "test", "validate"]
    assert data["assets"][1]["sha256"] == data["assets"][1]["source_sha256"]


def test_presentation_is_only_a_crop_or_exact_supplied_copy(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    target = tmp_path / "presentation"
    manifest = presentation.export(target)
    source = presentation.REPO_ROOT / manifest["assets"][0]["source"]
    with Image.open(source) as original, Image.open(target / "readme-hero.png") as derived:
        assert derived.size == (587, 253)
        assert derived.tobytes() == original.crop(presentation.CROP).tobytes()
        with Image.open(
            presentation.REPO_ROOT / presentation.PRESENTATION / "readme-hero.png"
        ) as committed:
            assert committed.tobytes() == original.crop(presentation.CROP).tobytes()
    with Image.open(target / "github-social.png") as social:
        assert social.size == (1280, 640)
    with pytest.raises(OCFError, match="already exists"):
        presentation.export(target)


@pytest.mark.parametrize(
    "source", [".ocf-work/private.png", "../outside.png", "https://images.example.invalid/logo.png"]
)
def test_readme_rejects_private_escaping_or_external_artwork_paths(tmp_path, source):
    (tmp_path / "README.md").write_text(f"![OCF]({source})", encoding="utf-8")
    with pytest.raises(OCFError, match="image|repository"):
        presentation.check_readme(tmp_path)


def test_default_album_theme_is_imported_dark_without_changing_ui_or_documentation():
    assert artwork.theme_tokens("artwork")["theme"]["id"] == "ocf-cosmic-dark"
    assert artwork.theme_tokens("ui")["theme"]["id"] == "ocf-light"
    assert artwork.theme_tokens("documentation")["theme"]["id"] == "ocf-minimal"
    assert artwork.identity()["version"] == "0.1.0"


@pytest.mark.unit
def test_local_untracked_readme_image_cannot_pass_a_clean_checkout_guard(tmp_path, monkeypatch):
    from types import SimpleNamespace

    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    badges = []
    for name in ("lint", "validate", "generated-index-check", "test"):
        (workflows / (name + ".yml")).write_text("name: " + name, encoding="utf-8")
        badges.append(
            f"![{name}](https://github.com/meramsey/open-consciousness-functions/actions/workflows/{name}.yml/badge.svg)"
        )
    (tmp_path / "hero.png").write_bytes(b"locally present but untracked")
    (tmp_path / "README.md").write_text("![OCF](hero.png)\n" + "\n".join(badges), encoding="utf-8")
    monkeypatch.setattr(
        presentation, "workspace_run", lambda *_a, **_k: SimpleNamespace(returncode=1)
    )
    with pytest.raises(OCFError, match="Git-tracked"):
        presentation.check_readme(tmp_path)


def test_function_theme_explicit_override_cache_and_existing_cover_preservation(
    monkeypatch, tmp_path
):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    first = artwork.generate_cover("OCF-SLP-005", resolution=320)
    assert first["settings"]["brand"]["version"] == "0.3.0"
    assert first["settings"]["theme"]["id"] == "ocf-cosmic-dark"
    first_path = Path(first["path"])
    old_sha = sha256_of_file(first_path)
    record = deepcopy(artwork.load_function_by_id("OCF-SLP-005"))
    record.data["audio"]["artwork_theme"] = "ocf-cosmic-light"
    monkeypatch.setattr(artwork, "load_function_by_id", lambda _: record)
    configured = artwork.generate_cover("OCF-SLP-005", resolution=320)
    assert configured["settings"]["theme_selection"] == "function"
    assert configured["settings"]["theme"]["id"] == "ocf-cosmic-light"
    explicit = artwork.generate_cover(
        "OCF-SLP-005", resolution=320, theme="ocf-cosmic-minimal", format="jpeg"
    )
    assert explicit["settings"]["theme_selection"] == "explicit"
    assert explicit["settings"]["theme"]["id"] == "ocf-cosmic-minimal"
    assert first["fingerprint"] != configured["fingerprint"] != explicit["fingerprint"]
    assert sha256_of_file(first_path) == old_sha
    assert artwork.generate_cover("OCF-SLP-005", resolution=320)["cache"] == "hit"


def test_release_implementation_theme_and_custom_cover_precedence(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    manifest = {
        "id": "OCF-AUDIO-9000",
        "function_id": "OCF-SLP-005",
        "artwork_theme": "ocf-cosmic-light",
    }
    monkeypatch.setattr(release, "_select_audio_manifest", lambda _: manifest)
    configured = release.package_release(
        "OCF-SLP-005", artwork_resolution=320, dry_run=True, output=tmp_path / "out"
    )
    assert configured["artwork_provenance"]["theme_id"] == "ocf-cosmic-light"
    assert configured["artwork_provenance"]["theme_selection"] == "audio-implementation"
    explicit = release.package_release(
        "OCF-SLP-005",
        artwork_theme="ocf-cosmic-dark",
        artwork_resolution=320,
        dry_run=True,
        output=tmp_path / "out",
    )
    assert explicit["artwork_provenance"]["theme_id"] == "ocf-cosmic-dark"
    cover = artwork.generate_cover("OCF-SLP-005", resolution=320)
    manifest["artwork_theme"] = "missing-theme"
    custom = release.package_release(
        "OCF-SLP-005",
        artwork=cover["path"],
        artwork_theme="also-missing",
        dry_run=True,
        output=tmp_path / "out",
    )
    assert custom["artwork_provenance"]["source"] == "explicit-user-cover"
    assert custom["artwork_provenance"]["publication_approval"] is False


@pytest.mark.unit
def test_mcp_artwork_omission_preserves_inherited_selection(monkeypatch):
    from ocf_tools import dev_jobs

    captured = []
    monkeypatch.setattr(
        dev_jobs, "start", lambda operation, args: captured.append((operation, args)) or {}
    )
    agent_api.generate_artwork_preview("OCF-SLP-005")
    assert captured[0][1]["theme"] is None


def test_mcp_preview_function_theme_parity_and_explicit_override(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from ocf_tools import dev_jobs

    record = deepcopy(artwork.load_function_by_id("OCF-SLP-005"))
    record.data["audio"]["artwork_theme"] = "ocf-cosmic-light"
    monkeypatch.setattr(agent_api, "owner", lambda _: record)
    monkeypatch.setattr(artwork, "load_function_by_id", lambda _: record)
    args = dev_jobs.validate_request(
        "artwork", {"function_id": record.id, "theme": None, "resolution": 320}
    )
    assert args["theme"] is None
    generated = artwork.generate_cover(**args, dry_run=True)
    assert generated["settings"]["theme"]["id"] == "ocf-cosmic-light"
    assert generated["settings"]["theme_selection"] == "function"
    args["theme"] = "ocf-cosmic-dark"
    assert artwork.generate_cover(**args, dry_run=True)["settings"]["theme_selection"] == "explicit"


def test_configured_release_theme_is_accepted_by_cli_service_and_mcp_preflight(monkeypatch):
    from ocf_tools import dev_jobs

    manifest = {
        "id": "OCF-AUDIO-9000",
        "function_id": "OCF-SLP-005",
        "artwork_theme": "ocf-cosmic-light",
    }
    monkeypatch.setattr(release, "_select_audio_manifest", lambda _: manifest)
    captured = []
    monkeypatch.setattr(
        dev_jobs,
        "start",
        lambda operation, args: captured.append((operation, args)) or {"status": "planned"},
    )
    assert agent_api.package_release("OCF-SLP-005")["status"] == "planned"
    assert captured[0][1]["artwork_theme"] is None
    validated = dev_jobs.validate_request("release", captured[0][1])
    assert validated["artwork_theme"] is None
    assert release.artwork_selection("OCF-SLP-005")[2:] == (
        "ocf-cosmic-light",
        "audio-implementation",
    )


@pytest.mark.parametrize("mutation", ["hero", "crop", "source"])
def test_forged_presentation_provenance_cannot_pass_even_with_updated_hash(
    tmp_path, monkeypatch, mutation
):
    pytest.importorskip("PIL")
    from PIL import Image

    directory = tmp_path / presentation.PRESENTATION
    directory.mkdir(parents=True)
    original_dir = presentation.REPO_ROOT / presentation.PRESENTATION
    for source in original_dir.iterdir():
        shutil.copyfile(source, directory / source.name)
    data = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for asset in data["assets"]:
        target = tmp_path / asset["source"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(presentation.REPO_ROOT / asset["source"], target)
    monkeypatch.setattr(
        presentation, "verify", lambda _: {"manifest_sha256": data["kit_manifest_sha256"]}
    )
    if mutation == "hero":
        Image.new("RGB", (587, 253)).save(directory / "readme-hero.png")
        data["assets"][0]["sha256"] = sha256_of_file(directory / "readme-hero.png")
    elif mutation == "crop":
        data["hero_crop"][1] = 0
    else:
        data["assets"][0]["source"] = data["assets"][1]["source"]
    (directory / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OCFError, match="crop|bindings"):
        presentation.check_assets(tmp_path)
