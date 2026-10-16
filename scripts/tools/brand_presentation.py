"""Versioned presentation exports from supplied artwork; never redraw original art."""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocf_tools.brand_import import source_root, verify  # noqa: E402
from ocf_tools.paths import REPO_ROOT, workspace_run  # noqa: E402
from ocf_tools.utils import OCFError, sha256_of_file, write_text_atomic  # noqa: E402

PRESENTATION = Path("brand/versions/0.3.0/presentation")
CROP = (1, 28, 588, 281)
HERO_SHA256 = "d91f5bd8c03b8e56ef39b6aef5ffb94b0d8407a0a8b81beacc2fda2c17bf0189"
SOURCE_BINDINGS = {
    "readme-hero.png": "brand/imports/ocf-cosmic-path-brand-kit-v1/reference/cinematic-dark-logo-reference.png",
    "github-social.png": "brand/imports/ocf-cosmic-path-brand-kit-v1/png/ocf-github-social-1280x640.png",
}


def export(output: Path):
    from PIL import Image

    verification = verify()
    if output.exists() and any(path.name != "README.md" for path in output.iterdir()):
        raise OCFError("presentation directory already exists; never overwrite candidate exports")
    output.mkdir(parents=True, exist_ok=True)
    supplied = source_root()
    hero_source = supplied / "reference/cinematic-dark-logo-reference.png"
    social_source = supplied / "png/ocf-github-social-1280x640.png"
    with Image.open(hero_source) as image:
        buffer = io.BytesIO()
        image.crop(CROP).save(buffer, format="PNG", compress_level=9)
        with (output / "readme-hero.png").open("xb") as target:
            target.write(buffer.getvalue())
    with (output / "github-social.png").open("xb") as target, social_source.open("rb") as source:
        shutil.copyfileobj(source, target)
    assets = []
    for name, source, method in (
        (
            "readme-hero.png",
            hero_source,
            "crop supplied cinematic reference; remove panel label/border; no redraw or upscaling",
        ),
        ("github-social.png", social_source, "unchanged supplied native 1280x640 PNG companion"),
    ):
        assets.append(
            {
                "path": name,
                "sha256": sha256_of_file(output / name),
                "source": source.relative_to(REPO_ROOT).as_posix(),
                "source_sha256": sha256_of_file(source),
                "method": method,
            }
        )
    manifest = {
        "schema_version": "1.0",
        "brand_version": "0.3.0",
        "presentation_revision": "1.0.0",
        "review_status": "candidate",
        "human_approval": None,
        "kit_manifest_sha256": verification["manifest_sha256"],
        "hero_crop": list(CROP),
        "limitations": "Cinematic reference crop has native 587x253 pixels; it is repository presentation, not a high-resolution cinematic album master. Supplied vector/raster companions are not exact copies of the cinematic reference.",
        "assets": assets,
    }
    write_text_atomic(
        output / "manifest.json", json.dumps(manifest, indent=2) + "\n", overwrite=False
    )
    return manifest


def check_assets(root=REPO_ROOT, directory=None):
    directory = Path(directory) if directory is not None else root / PRESENTATION
    data = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    supplied = verify(root / "brand/imports/ocf-cosmic-path-brand-kit-v1")
    if data["kit_manifest_sha256"] != supplied["manifest_sha256"]:
        raise OCFError("presentation must retain the verified supplied-kit provenance")
    if (
        data["human_approval"] is not None
        or data["review_status"] != "candidate"
        or data["brand_version"] != "0.3.0"
    ):
        raise OCFError("presentation must retain unapproved brand candidate status")
    expected = {"readme-hero.png", "github-social.png", "manifest.json"}
    if (directory / "README.md").is_file():
        expected.add("README.md")
    if directory.resolve() == (root / PRESENTATION).resolve() and "README.md" not in expected:
        raise OCFError("registered presentation needs its provenance/setup guide")
    if set(path.name for path in directory.iterdir()) != expected:
        raise OCFError("unexpected presentation inventory")
    assets = {asset["path"]: asset for asset in data["assets"]}
    if set(assets) != {"readme-hero.png", "github-social.png"} or len(data["assets"]) != 2:
        raise OCFError("presentation asset declarations must match both supplied compositions")
    if data["hero_crop"] != list(CROP) or any(
        assets[name]["source"] != source for name, source in SOURCE_BINDINGS.items()
    ):
        raise OCFError("presentation must retain the actual supplied source bindings and crop")
    for asset in assets.values():
        path = (directory / asset["path"]).resolve()
        source = (root / asset["source"]).resolve()
        if not path.is_relative_to(directory.resolve()) or not source.is_relative_to(
            root.resolve()
        ):
            raise OCFError("presentation path escapes repository")
        if (
            sha256_of_file(path) != asset["sha256"]
            or sha256_of_file(source) != asset["source_sha256"]
        ):
            raise OCFError("presentation/source checksum mismatch")
    if (directory / "github-social.png").read_bytes() != (
        root / assets["github-social.png"]["source"]
    ).read_bytes():
        raise OCFError("social preview must remain the unchanged supplied composition")
    if sha256_of_file(directory / "readme-hero.png") != HERO_SHA256:
        try:
            from PIL import Image

            with (
                Image.open(root / SOURCE_BINDINGS["readme-hero.png"]) as original,
                Image.open(directory / "readme-hero.png") as derived,
            ):
                expected_pixels = original.crop(CROP).convert("RGBA")
                if (
                    derived.size != expected_pixels.size
                    or derived.convert("RGBA").tobytes() != expected_pixels.tobytes()
                ):
                    raise OCFError("presentation hero is not the declared supplied-reference crop")
        except ImportError as exc:
            raise OCFError(
                "hero differs from pinned export; install artwork extra to verify crop pixels"
            ) from exc
    return data


class _Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "img":
            self.images.append((values.get("alt", ""), values.get("src", "")))


def check_readme(root=REPO_ROOT):
    text = (root / "README.md").read_text(encoding="utf-8")
    parser = _Images()
    parser.feed(text)
    images = parser.images + re.findall(r"!\[([^\]]*)\]\(([^)\s]+)\)", text)
    if not images:
        raise OCFError("README has no presentation images")
    badges = set()
    local_images = []
    for alt, source in images:
        if not alt.strip():
            raise OCFError("README images need meaningful alt text")
        url = urlparse(source)
        if url.scheme or url.netloc:
            match = re.fullmatch(
                r"https://github.com/meramsey/open-consciousness-functions/actions/workflows/([a-z-]+)\.yml/badge\.svg",
                source,
            )
            if not match or not (root / ".github/workflows" / (match.group(1) + ".yml")).is_file():
                raise OCFError("README remote images must be actual repository Actions badges")
            badges.add(match.group(1))
            continue
        relative = unquote(source)
        path = (root / relative).resolve()
        if (
            relative.startswith(".ocf-work/")
            or not path.is_relative_to(root.resolve())
            or not path.is_file()
        ):
            raise OCFError("README image is missing, private or outside repository")
        local_images.append(path.relative_to(root.resolve()).as_posix())
    if badges != {"lint", "validate", "generated-index-check", "test"}:
        raise OCFError("README must link all four actual workflow badges")
    tracked = workspace_run(
        ["git", "ls-files", "--error-unmatch", "--", *local_images],
        cwd=root,
        capture_output=True,
        timeout=10,
    )
    if tracked.returncode:
        raise OCFError("README images must be Git-tracked assets, not merely present locally")
    return {"images": len(images), "workflow_badges": sorted(badges)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / PRESENTATION)
    args = parser.parse_args(argv)
    if args.write:
        result = export(args.output)
    else:
        data = check_assets(directory=args.output)
        result = (
            check_readme()
            if args.output.resolve() == (REPO_ROOT / PRESENTATION).resolve()
            else {
                "status": "passed",
                "brand_version": data["brand_version"],
                "human_approval": None,
            }
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
