"""Patched dependency floors and narrow parser/CI boundaries, without exploit payloads."""

import re
import tomllib

import pytest
import yaml
from conftest import REPO_ROOT
from ocf_tools import audition_exports, bootstrap
from ocf_tools.utils import OCFError
from packaging.requirements import Requirement


def requirements(values):
    return {req.name.lower(): req for req in map(Requirement, values)}


@pytest.mark.integration
def test_security_versions_match_all_supported_installation_groups():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = project["project"]["optional-dependencies"]
    dev = requirements((REPO_ROOT / "requirements-dev.txt").read_text().splitlines())
    for group in (extras["artwork"], extras["guides"], extras["dev"]):
        assert str(requirements(group)["pillow"].specifier) == "==13.0.0"
    assert str(dev["pillow"].specifier) == "==13.0.0"
    assert "pillow" not in requirements(project["project"]["dependencies"])
    for group in (extras["dev"], (REPO_ROOT / "requirements-dev.txt").read_text().splitlines()):
        specs = requirements(group)
        assert "9.0.2" not in specs["pytest"].specifier
        assert "9.0.3" in specs["pytest"].specifier
        assert "83.0.0" not in specs["setuptools"].specifier
        assert "84.1.0" in specs["setuptools"].specifier
    build = requirements(project["build-system"]["requires"])
    assert "83.0.0" not in build["setuptools"].specifier
    assert "84.1.0" in build["setuptools"].specifier


@pytest.mark.integration
def test_every_ci_pip_install_bootstraps_patched_pip_first():
    command = "python -m pip install --only-binary=:all: --upgrade pip==26.2.0"
    assert bootstrap.PIP_REQUIREMENT == "pip==26.2.0"
    assert "--only-binary=:all: --upgrade pip==26.2.0" in (REPO_ROOT / "Dockerfile").read_text()
    for path in (REPO_ROOT / ".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow["jobs"].values():
            installs = [
                step["run"].strip()
                for step in job["steps"]
                if "python -m pip install" in step.get("run", "")
            ]
            if installs:
                assert installs[0] == command, path


@pytest.mark.integration
def test_dependency_review_blocks_high_and_critical_in_every_scope_without_write_access():
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/dependency-review.yml").read_text())
    assert set(workflow.get("on", workflow.get(True))) == {"pull_request"}
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["dependency-review"]["steps"]
    assert all(
        "run" not in step and re.fullmatch(r"[^@]+@[a-f0-9]{40}", step["uses"]) for step in steps
    )
    policy = steps[-1]["with"]
    assert policy["fail-on-severity"] == "high"
    assert {scope.strip() for scope in policy["fail-on-scopes"].split(",")} == {
        "runtime",
        "development",
        "unknown",
    }
    assert policy["vulnerability-check"] == "true" and policy["warn-only"] == "false"
    assert policy["comment-summary-in-pr"] == "never"
    assert not any(key.startswith(("allow-", "deny-")) for key in policy)


@pytest.mark.unit
def test_custom_jpeg_uses_only_jpeg_decoder_and_produces_rgb_png(monkeypatch, tmp_path):
    from PIL import Image

    source, destination = tmp_path / "cover.jpg", tmp_path / "cover.png"
    Image.new("RGB", (320, 320), "navy").save(source, "JPEG")
    original = source.read_bytes()
    real_open = Image.open

    def guarded_open(path, *args, formats=None, **kwargs):
        assert formats == ("JPEG",)
        return real_open(path, *args, formats=formats, **kwargs)

    monkeypatch.setattr(Image, "open", guarded_open)
    audition_exports.copy_cover(source, destination)
    with real_open(destination) as result:
        assert result.format == "PNG" and result.mode == "RGB" and result.size == (320, 320)
    assert source.read_bytes() == original


@pytest.mark.unit
def test_custom_png_copy_is_byte_identical_and_does_not_decode(monkeypatch, tmp_path):
    from PIL import Image

    source, destination = tmp_path / "source.png", tmp_path / "copy.png"
    Image.new("RGB", (320, 320), "navy").save(source)
    monkeypatch.setattr(
        Image, "open", lambda *args, **kwargs: pytest.fail("PNG copy decoded input")
    )
    audition_exports.copy_cover(source, destination)
    assert destination.read_bytes() == source.read_bytes()


@pytest.mark.unit
def test_truncated_jpeg_with_valid_dimensions_never_publishes_a_cover(tmp_path):
    from PIL import Image

    source, destination = tmp_path / "bad.jpg", tmp_path / "copy.png"
    Image.new("RGB", (320, 320), "navy").save(source, "JPEG")
    data = source.read_bytes()
    marker = data.index(b"\xff\xc0")
    source.write_bytes(data[: marker + 2 + int.from_bytes(data[marker + 2 : marker + 4], "big")])
    assert audition_exports._image_info(source)[1:] == (320, 320)
    with pytest.raises(OSError):
        audition_exports.copy_cover(source, destination)
    assert not destination.exists()


@pytest.mark.unit
def test_jpeg_header_and_decoded_dimensions_must_agree(monkeypatch, tmp_path):
    from PIL import Image

    source, destination = tmp_path / "cover.jpg", tmp_path / "copy.png"
    Image.new("RGB", (320, 320), "navy").save(source, "JPEG")
    monkeypatch.setattr(Image, "open", lambda *args, **kwargs: Image.new("RGB", (321, 320)))
    with pytest.raises(OCFError, match="dimensions changed"):
        audition_exports.copy_cover(source, destination)
    assert not destination.exists()
