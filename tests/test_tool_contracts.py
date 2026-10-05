"""Isolated contracts for deterministic first-party research and packaging tools."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools.utils import OCFError
from tools import (
    bootstrap_legacy_map,
    check_markdown_links,
    container_smoke_fixture,
    enrich_function_evidence,
    preview_preparation_learning,
    render_development_v2,
)


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
    import sys

    script = Path(bootstrap_legacy_map.__file__).resolve()
    isolated_root = tmp_path / "isolated"
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path.name == "bootstrap_legacy_map.py" and path.parent.name == "tools":
            return isolated_root / "scripts/tools/bootstrap_legacy_map.py"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(sys, "argv", [str(script)])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script), run_name="__main__")
    assert exit_info.value.code == 0
    assert len(list((isolated_root / "functions").rglob("*.yaml"))) == 55
    assert "Wrote 55 function records" in capsys.readouterr().out


@pytest.mark.unit
def test_legacy_bootstrap_script_guard_routes_only_to_injected_writer(monkeypatch):
    import runpy
    import sys

    from ocf_tools import utils

    writes = []
    monkeypatch.setattr(
        utils, "write_text_atomic", lambda path, content: writes.append((path, content))
    )
    monkeypatch.setattr(sys, "argv", [bootstrap_legacy_map.__file__])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(bootstrap_legacy_map.__file__, run_name="__main__")
    assert exit_info.value.code == 0
    assert len(writes) == 55
    assert all("/functions/" in str(path) for path, _ in writes)


@pytest.mark.unit
@pytest.mark.parametrize("failure", ["changed-rc1", "speech-checksum", "output-exists"])
def test_frozen_audition_renderer_preflights_inputs_before_any_output(
    monkeypatch, tmp_path, failure
):
    import hashlib
    import sys

    import yaml

    v1 = tmp_path / "v1"
    v1.mkdir()
    source = v1 / "V1-narration.wav"
    source.write_bytes(b"preserved V1 bytes")
    output = tmp_path / "audition"
    expected_speech_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    rc1 = tmp_path / "locales/en-US/functions.yaml"
    rc1.parent.mkdir(parents=True)
    rc1.write_bytes(b"frozen RC1 source")
    rc1_hash = hashlib.sha256(rc1.read_bytes()).hexdigest()
    manifest = {
        "rc1_source_sha256": {"locales/en-US/functions.yaml": rc1_hash},
        "artifacts": {source.name: {"sha256": expected_speech_hash}},
    }
    if failure == "changed-rc1":
        rc1.write_bytes(b"changed RC1")
    elif failure == "speech-checksum":
        manifest["artifacts"][source.name]["sha256"] = "0" * 64
    else:
        output.mkdir()
        for name in (
            "session-semantic.yaml",
            "session-resolved.en-US.yaml",
            "resolved-semantic-event-ledger.yaml",
            "narration-render-metadata.yaml",
            "timing-report.yaml",
            "utterance-timing.csv",
            "subtitle.srt",
            "subtitle.lrc",
        ):
            (v1 / name).write_text("synthetic input", encoding="utf-8")
    (v1 / "render-manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    monkeypatch.setattr(render_development_v2, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_development_v2", "--v1", str(v1), "--output", str(output)],
    )
    message = (
        "RC1 source changed"
        if failure == "changed-rc1"
        else ("V1 speech checksum" if failure == "speech-checksum" else "refusing to overwrite")
    )
    with pytest.raises(RuntimeError, match=message):
        render_development_v2.main()
    if failure != "output-exists":
        assert not output.exists()


@pytest.mark.unit
def test_frozen_audition_renderer_preflights_all_copied_files_before_creating_output(
    monkeypatch, tmp_path
):
    import hashlib
    import sys

    import yaml

    v1 = tmp_path / "v1"
    v1.mkdir()
    source = v1 / "V1-narration.wav"
    source.write_bytes(b"preserved V1 bytes")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    (v1 / "render-manifest.yaml").write_text(
        yaml.safe_dump({"rc1_source_sha256": {}, "artifacts": {source.name: {"sha256": expected}}}),
        encoding="utf-8",
    )
    output = tmp_path / "audition"
    monkeypatch.setattr(render_development_v2, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_development_v2", "--v1", str(v1), "--output", str(output)],
    )
    with pytest.raises(RuntimeError, match="V1 artifact unavailable: session-semantic.yaml"):
        render_development_v2.main()
    assert not output.exists()


@pytest.mark.unit
def test_frozen_audition_renderer_preflights_subtitles_before_creating_output(
    monkeypatch, tmp_path
):
    import hashlib
    import sys

    import yaml

    v1 = tmp_path / "v1"
    v1.mkdir()
    source = v1 / "V1-narration.wav"
    source.write_bytes(b"preserved V1 bytes")
    for name in (
        "session-semantic.yaml",
        "session-resolved.en-US.yaml",
        "resolved-semantic-event-ledger.yaml",
        "narration-render-metadata.yaml",
        "timing-report.yaml",
        "utterance-timing.csv",
        "existing.srt",
    ):
        (v1 / name).write_text("synthetic V1 input", encoding="utf-8")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    (v1 / "render-manifest.yaml").write_text(
        yaml.safe_dump({"rc1_source_sha256": {}, "artifacts": {source.name: {"sha256": expected}}}),
        encoding="utf-8",
    )
    output = tmp_path / "audition"
    monkeypatch.setattr(render_development_v2, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_development_v2", "--v1", str(v1), "--output", str(output)],
    )
    with pytest.raises(RuntimeError, match=r"V1 subtitle unavailable: \*\.lrc"):
        render_development_v2.main()
    assert not output.exists()


@pytest.mark.unit
def test_development_verifier_reads_only_synthetic_pcm_for_basic_statistics(tmp_path):
    import hashlib
    import importlib
    import math
    import wave
    from array import array

    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    pytest.importorskip("soundfile")
    verifier = importlib.import_module("tools.verify_development_v2")
    path = tmp_path / "synthetic.wav"
    with wave.open(str(path), "wb") as writer:
        writer.setparams((2, 2, 8000, 0, "NONE", "not compressed"))
        writer.writeframes(b"\x00\x40\x00\xc0" * 800)
    assert verifier.db(0) == -400
    assert verifier.db(0.5) == pytest.approx(-6.0206, abs=0.001)
    block, sample_rate = verifier.block(path, 0.025, 0.01)
    assert sample_rate == 8000 and block.shape == (80, 2)
    measured = verifier.stats(path)
    assert measured["frames"] == 800
    assert measured["duration_s"] == pytest.approx(0.1)
    assert measured["channels"] == 2 and measured["clipped_samples"] == 0
    assert measured["peak_dbfs"] == pytest.approx(-6.0206, abs=0.001)
    assert verifier._sha(path) == hashlib.sha256(path.read_bytes()).hexdigest()

    sample_rate = 8000
    samples = array("h")
    for index in range(sample_rate * 4):
        samples.extend(
            (
                int(0.5 * 32767 * math.sin(2 * math.pi * 40 * index / sample_rate)),
                0,
            )
        )
    tone = tmp_path / "synthetic-tone.wav"
    with wave.open(str(tone), "wb") as writer:
        writer.setparams((2, 2, sample_rate, 0, "NONE", "not compressed"))
        writer.writeframes(samples.tobytes())
    measured_tone = verifier.amplitudes(tone, 0, 4, [40])[40]
    assert abs(measured_tone[0]) == pytest.approx(0.5, abs=0.01)
    assert verifier.window_rms(tone, 0, 4) == pytest.approx(-9.0309, abs=0.01)


@pytest.mark.unit
def test_verifier_approach_metrics_match_declared_curve_on_synthetic_measurements(monkeypatch):
    import importlib

    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    pytest.importorskip("soundfile")
    verifier = importlib.import_module("tools.verify_development_v2")
    fractions = (0.125, 0.25, 0.5, 0.75)
    starts = {fraction: 10 * fraction for fraction in fractions}
    sustained = -20.0

    def window_rms(_bed, start, _seconds):
        for fraction, probe_start in starts.items():
            if abs(start - probe_start) < 1e-12:
                expected = verifier.db((1 - verifier.np.cos(verifier.np.pi * fraction)) / 2)
                return sustained + expected
        return sustained

    def amplitudes(_bed, start, _seconds, frequencies):
        level = 0.01 if start < 20 else 1.0
        return {frequency: verifier.np.array([level, level]) for frequency in frequencies}

    monkeypatch.setattr(verifier, "window_rms", window_rms)
    monkeypatch.setattr(verifier, "amplitudes", amplitudes)
    approach = {
        "start_s": 0,
        "established_s": 10,
        "arrival_s": 20,
        "begin_semantic": "synthetic.begin",
        "state": "synthetic-state",
    }
    result = verifier.approach_rise("synthetic-bed", [approach], 40)
    assert result[0]["approach"] == "synthetic.begin"
    assert [probe["approach_fraction"] for probe in result[0]["probes"]] == list(fractions)
    assert all(
        probe["measured_relative_db"] == pytest.approx(probe["declared_raised_cosine_relative_db"])
        for probe in result[0]["probes"]
    )
    with pytest.raises(AssertionError):
        verifier.approach_rise("synthetic-bed", [{**approach, "arrival_s": 9}], 40)


@pytest.mark.unit
@pytest.mark.parametrize(
    "script",
    [
        "tools/analyze_v4_short.py",
        "tools/render_development_v2.py",
        "tools/verify_development_v2.py",
    ],
)
def test_research_entrypoint_guards_enter_main_without_running_external_work(monkeypatch, script):
    import argparse
    import runpy

    if script.endswith(("analyze_v4_short.py", "verify_development_v2.py")):
        pytest.importorskip("numpy")
        pytest.importorskip("scipy")
        pytest.importorskip("soundfile")

    class StopBeforeInputs(Exception):
        pass

    def stop(_parser, *_args, **_kwargs):
        raise StopBeforeInputs

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", stop)
    path = Path(__file__).resolve().parents[1] / "scripts" / script
    with pytest.raises(StopBeforeInputs):
        runpy.run_path(str(path), run_name="__main__")


@pytest.mark.unit
def test_evidence_enrichment_only_adds_hash_addressed_documentary_links():
    layers = {
        "evidence": {
            "sources": [
                {"sha256": "a" * 64, "evidence_class": "unknown"},
                {"sha256": "b" * 64, "evidence_class": "source_transcript"},
                {"sha256": "c" * 64, "evidence_class": "unknown"},
            ]
        }
    }
    report = {
        "files": [
            {
                "sha256": "a" * 64,
                "evidence_class": "secondary_description",
                "content_sha256": "d" * 64,
            },
            {"sha256": "b" * 64, "evidence_class": "secondary_description", "content_sha256": None},
        ],
        "content_equivalence_groups": [{"representations": ["a" * 64, "f" * 64, "e" * 64]}],
    }
    result = enrich_function_evidence.enrich(layers, report)
    assert result["evidence"]["sources"][0] == {
        "sha256": "a" * 64,
        "evidence_class": "secondary_description",
        "normalized_content_sha256": "d" * 64,
        "related_sha256": ["e" * 64, "f" * 64],
    }
    assert result["evidence"]["sources"][1]["evidence_class"] == "source_transcript"
    assert result["evidence"]["sources"][1]["related_sha256"] == []
    assert result["evidence"]["sources"][2] == {
        "sha256": "c" * 64,
        "evidence_class": "unknown",
    }


@pytest.mark.unit
def test_evidence_enrichment_cli_validates_by_default_and_applies_explicitly(
    monkeypatch, tmp_path, capsys
):
    import json
    import sys

    record = SimpleNamespace(id="OCF-TST-001")
    layer_data = {"evidence": {"sources": []}}
    report = {"files": [], "content_equivalence_groups": []}
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    written = []
    monkeypatch.setattr(enrich_function_evidence, "ROOT", tmp_path)
    monkeypatch.setattr(enrich_function_evidence, "load_all_functions", lambda: [record])
    monkeypatch.setattr(enrich_function_evidence, "load_layers", lambda _id: layer_data)
    monkeypatch.setattr(enrich_function_evidence, "validate_layers", lambda *_args: [])
    monkeypatch.setattr(
        enrich_function_evidence,
        "write_text_atomic",
        lambda path, text: written.append((path, text)),
    )
    monkeypatch.setattr(sys, "argv", ["enrich_function_evidence", str(report_path)])
    enrich_function_evidence.main()
    assert not written
    assert "Validated documentary refinements" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["enrich_function_evidence", str(report_path), "--apply"])
    enrich_function_evidence.main()
    assert written and written[0][0] == tmp_path / "function-content/evidence/OCF-TST-001.yaml"

    import runpy

    from ocf_tools import indexes

    monkeypatch.setattr(enrich_function_evidence, "validate_layers", lambda *_args: ["bad layer"])
    monkeypatch.setattr(sys, "argv", ["enrich_function_evidence", str(report_path)])
    with pytest.raises(OCFError, match="bad layer"):
        enrich_function_evidence.main()
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [])
    runpy.run_path(str(Path(enrich_function_evidence.__file__)), run_name="__main__")
    assert "no authentication or wording changes" in capsys.readouterr().out


@pytest.mark.unit
def test_preparation_preview_preflight_and_writer_safety_use_only_synthetic_text(
    monkeypatch, tmp_path, capsys
):
    from ocf_tools.utils import OCFError

    with pytest.raises(OCFError, match="words per minute"):
        preview_preparation_learning.build_preview(words_per_minute=0)
    with pytest.raises(OCFError, match="optional stages"):
        preview_preparation_learning.build_preview(include_optional=False, affirmation="synthetic")

    synthetic = {
        "listener": f"{preview_preparation_learning.BANNER}\nSynthetic listener fixture.\n",
        "developer": f"{preview_preparation_learning.BANNER}\nSynthetic developer fixture.\n",
        "stats": {"spoken_words": 3},
    }
    observed = {}
    monkeypatch.setattr(
        preview_preparation_learning,
        "build_preview",
        lambda **kwargs: observed.update(kwargs) or synthetic,
    )
    output = tmp_path / "drafts"
    assert (
        preview_preparation_learning.main(["--output-dir", str(output), "--without-optional"]) == 0
    )
    assert observed == {"include_optional": False, "affirmation": None, "words_per_minute": 140}
    listener = output / "preparation-learning.en-US.listener.md"
    developer = output / "preparation-learning.en-US.developer.md"
    assert listener.read_text() == synthetic["listener"]
    assert developer.read_text() == synthetic["developer"]

    assert preview_preparation_learning.main(["--output-dir", str(output), "--check"]) == 0
    listener.write_text("stale content", encoding="utf-8")
    assert preview_preparation_learning.main(["--output-dir", str(output), "--check"]) == 1
    assert "text preview is stale" in capsys.readouterr().err
    listener.write_text("unrelated editor document", encoding="utf-8")
    assert preview_preparation_learning.main(["--output-dir", str(output)]) == 1
    assert "refusing to overwrite an unrelated file" in capsys.readouterr().err


@pytest.mark.unit
def test_preparation_preview_renderer_formats_synthetic_event_data_only(monkeypatch):
    template = {
        "name": "Synthetic preview template",
        "sections": [{"id": "affirmation", "narration": {}}],
    }
    doc = {
        "timeline": [
            {
                "id": f"event-{index}",
                "text": text,
                "semantic": f"synthetic.semantic.{index}",
                "timing": {"pause_after": pause},
                **({"at": 0} if index == 1 else {"after": f"event-{index - 1}"}),
            }
            for index, (text, pause) in enumerate(
                [
                    ("First synthetic phrase.", 0),
                    ("Second synthetic phrase.", 5),
                    ("Third synthetic phrase.", 15),
                    ("Fourth synthetic phrase.", 25),
                ],
                start=1,
            )
        ]
    }
    captured = {}
    resource = SimpleNamespace(
        file="preparation-learning.yaml", version="1.0", status="reviewed", notes="synthetic"
    )
    catalog = SimpleNamespace(
        canonical=SimpleNamespace(
            entries={
                "preparation.synthetic": resource,
                "function.learning.synthetic": resource,
                "unrelated.synthetic": SimpleNamespace(file="other.yaml"),
            }
        )
    )
    monkeypatch.setattr(preview_preparation_learning, "load_template", lambda _name: template)

    def compose(source, _slots, **kwargs):
        captured.update(template=source, **kwargs)
        return doc

    monkeypatch.setattr(preview_preparation_learning, "compose", compose)
    monkeypatch.setattr(
        preview_preparation_learning,
        "validate_timed_transcript",
        lambda *_args: SimpleNamespace(errors=[]),
    )
    monkeypatch.setattr(
        preview_preparation_learning,
        "schedule_timeline",
        lambda _doc, _estimates: [
            {"id": event["id"], "at": (index - 1) * 10, "end": index * 10}
            for index, event in enumerate(doc["timeline"], start=1)
        ],
    )
    monkeypatch.setattr(
        preview_preparation_learning,
        "bind_document_cues",
        lambda _doc: [
            {"event_id": "event-1", "identity": "synthetic.cue", "binding": {"mode": "disabled"}}
        ],
    )
    monkeypatch.setattr(preview_preparation_learning, "LocaleCatalog", lambda: catalog)

    result = preview_preparation_learning.build_preview(
        include_optional=True, affirmation="synthetic affirmation", words_per_minute=120
    )
    assert captured["enabled_stages"] == ["affirmation", "tuning"]
    assert template["sections"][0]["narration"]["practice"]["variables"] == {
        "affirmation": "synthetic affirmation"
    }
    assert result["stats"]["spoken_words"] == 12
    assert result["stats"]["explicit_pause_s"] == 45
    assert "Fourth synthetic phrase." in result["listener"]
    assert "25s (practice)" in result["developer"]
    assert "preparation.synthetic" in result["developer"]
    assert "unrelated.synthetic" not in result["developer"]


@pytest.mark.unit
def test_preparation_preview_reports_synthetic_transcript_validation_failures(monkeypatch):
    from ocf_tools.utils import OCFError

    monkeypatch.setattr(
        preview_preparation_learning,
        "load_template",
        lambda _name: {"name": "synthetic", "sections": []},
    )
    monkeypatch.setattr(preview_preparation_learning, "compose", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        preview_preparation_learning,
        "resolve_document",
        lambda *_args, **_kwargs: {"timeline": []},
    )
    monkeypatch.setattr(
        preview_preparation_learning,
        "validate_timed_transcript",
        lambda *_args: SimpleNamespace(
            errors=[SimpleNamespace(message="synthetic validation error")]
        ),
    )
    with pytest.raises(OCFError, match="synthetic validation error"):
        preview_preparation_learning.build_preview()


@pytest.mark.unit
def test_preparation_preview_script_entrypoint_emits_only_synthetic_fixture(monkeypatch, tmp_path):
    import runpy
    import sys

    from ocf_tools import locale, semantics, session, timing, transcript, validators

    document = {
        "timeline": [
            {
                "id": "fixture-event",
                "text": "Synthetic test phrase.",
                "semantic": "fixture.semantic",
                "at": 0,
                "timing": {"pause_after": 2},
            }
        ]
    }
    monkeypatch.setattr(
        session,
        "load_template",
        lambda _name: {"name": "Synthetic", "sections": [{"id": "affirmation", "narration": {}}]},
    )
    monkeypatch.setattr(session, "compose", lambda *_args, **_kwargs: document)
    monkeypatch.setattr(locale, "resolve_document", lambda doc, *_args, **_kwargs: doc)
    monkeypatch.setattr(locale, "iter_events", lambda doc: iter(doc["timeline"]))
    monkeypatch.setattr(
        validators, "validate_timed_transcript", lambda *_args: SimpleNamespace(errors=[])
    )
    monkeypatch.setattr(
        timing, "schedule_timeline", lambda *_args: [{"id": "fixture-event", "at": 0, "end": 4}]
    )
    monkeypatch.setattr(transcript, "format_timestamp", lambda _value: "00:00.000")
    monkeypatch.setattr(semantics, "bind_document_cues", lambda _doc: [])
    monkeypatch.setattr(
        preview_preparation_learning,
        "LocaleCatalog",
        lambda: SimpleNamespace(canonical=SimpleNamespace(entries={})),
    )
    output = tmp_path / "synthetic-preview"
    monkeypatch.setattr(sys, "argv", ["preview_preparation_learning", "--output-dir", str(output)])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(preview_preparation_learning.__file__)), run_name="__main__")
    assert exit_info.value.code == 0
    assert "Synthetic test phrase." in (
        output / "preparation-learning.en-US.listener.md"
    ).read_text(encoding="utf-8")
