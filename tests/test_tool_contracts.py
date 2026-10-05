"""Isolated contracts for deterministic first-party research and packaging tools."""

from pathlib import Path

import pytest
from tools import bootstrap_legacy_map, check_markdown_links, container_smoke_fixture


@pytest.mark.unit
def test_markdown_link_scanner_respects_source_ignores_and_internal_targets(monkeypatch, tmp_path):
    root = tmp_path / "root"
    (root / "docs").mkdir(parents=True)
    (root / ".private").mkdir()
    (root / "build").mkdir()
    (root / "references/HumanPlusTranscripts").mkdir(parents=True)
    (root / "ReusablePrompts").mkdir()
    (root / "docs/target.md").write_text("target", encoding="utf-8")
    (root / "docs/guide.md").write_text(
        "[local](target.md#part) [url](https://example.org) [anchor](#top) "
        "[query](?raw) [empty](#) [missing](absent.md)\n",
        encoding="utf-8",
    )
    for ignored in (
        ".private/hidden.md",
        "build/generated.md",
        "references/HumanPlusTranscripts/private.md",
        "ReusablePrompts/user.md",
    ):
        (root / ignored).write_text("ignored", encoding="utf-8")
    monkeypatch.setattr(check_markdown_links, "REPO_ROOT", root)
    names = {path.relative_to(root).as_posix() for path in check_markdown_links.iter_markdown()}
    assert names == {"docs/guide.md", "docs/target.md"}
    failures = check_markdown_links.check_file(root / "docs/guide.md")
    assert failures == [f"{root / 'docs/guide.md'}: broken internal link -> absent.md"]


@pytest.mark.unit
def test_markdown_link_scanner_read_errors_and_cli_status(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "missing.md"
    assert "cannot read" in check_markdown_links.check_file(missing)[0]

    source = tmp_path / "clean.md"
    source.write_text("[external](mailto:x@y) [same](#section) [query](?download) [empty]()\n")
    monkeypatch.setattr(check_markdown_links, "iter_markdown", lambda: [source])
    assert check_markdown_links.main() == 0
    assert capsys.readouterr().out.strip() == "Markdown internal links: OK"

    source.write_text("[broken](missing.md)\n")
    assert check_markdown_links.main() == 1
    assert "1 broken internal link(s)" in capsys.readouterr().err

    import runpy

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(check_markdown_links.__file__)), run_name="__main__")
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == "Markdown internal links: OK"


@pytest.mark.unit
def test_container_smoke_fixture_is_synthetic_deterministic_and_non_overwriting(
    monkeypatch, tmp_path, capsys
):
    import hashlib
    import json
    import runpy
    import sys
    import wave

    import yaml

    output = tmp_path / "fixture"
    monkeypatch.setattr(sys, "argv", ["container_smoke_fixture", str(output)])
    container_smoke_fixture.main()
    first = json.loads(capsys.readouterr().out)
    wav = output / "test.wav"
    with wave.open(str(wav), "rb") as reader:
        assert reader.getnframes() / reader.getframerate() == 0.1
    package = yaml.safe_load((output / "package.yaml").read_text(encoding="utf-8"))
    session = yaml.safe_load((output / "session.yaml").read_text(encoding="utf-8"))
    assert first["source_sha256"] == hashlib.sha256(wav.read_bytes()).hexdigest()
    assert package["recordings"]["test"]["sha256"] == first["source_sha256"]
    assert session["timeline"][0]["text"] == "Synthetic test fixture."
    original = wav.read_bytes()
    with pytest.raises(FileExistsError):
        container_smoke_fixture.main()
    assert wav.read_bytes() == original

    second = tmp_path / "entrypoint"
    monkeypatch.setattr(sys, "argv", ["container_smoke_fixture.py", str(second)])
    runpy.run_path(str(Path(container_smoke_fixture.__file__)), run_name="__main__")
    assert (
        json.loads(capsys.readouterr().out)["source_sha256"]
        == hashlib.sha256((second / "test.wav").read_bytes()).hexdigest()
    )


@pytest.mark.unit
def test_legacy_bootstrap_builds_all_frozen_mappings_and_reports_count(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(bootstrap_legacy_map, "REPO", tmp_path)
    monkeypatch.setattr(bootstrap_legacy_map, "current_date", lambda: "2026-10-04")
    records = [bootstrap_legacy_map.build_record(entry) for entry in bootstrap_legacy_map.E]
    assert len(records) == 55
    assert all(record["ocf"]["reimplementation_status"] == "planned" for record in records)
    assert {record["legacy"]["source_availability"] for record in records} == {
        "available",
        "unavailable",
    }
    assert any(record["safety"]["notes"] for record in records)
    assert all(record["version"]["created"] == "2026-10-04" for record in records)
    assert bootstrap_legacy_map.main() == 0
    assert len(list((tmp_path / "functions").rglob("*.yaml"))) == 55
    assert "Wrote 55 function records" in capsys.readouterr().out

    monkeypatch.setattr(bootstrap_legacy_map, "E", bootstrap_legacy_map.E[:1])
    assert bootstrap_legacy_map.main() == 1
    assert "expected 55, wrote 1" in capsys.readouterr().out


@pytest.mark.unit
def test_legacy_bootstrap_script_entrypoint_writes_only_to_temporary_root(
    tmp_path, capsys, monkeypatch
):
    import runpy
    import shutil
    import sys

    script_root = tmp_path / "isolated/scripts/tools"
    script_root.mkdir(parents=True)
    copied_script = script_root / "bootstrap_legacy_map.py"
    shutil.copyfile(bootstrap_legacy_map.__file__, copied_script)
    monkeypatch.setattr(sys, "argv", [str(copied_script)])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(copied_script), run_name="__main__")
    assert exit_info.value.code == 0
    assert len(list((tmp_path / "isolated/functions").rglob("*.yaml"))) == 55
    assert "Wrote 55 function records" in capsys.readouterr().out
