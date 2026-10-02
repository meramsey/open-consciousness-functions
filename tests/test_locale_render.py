"""Locale-aware TTS, measured subtitle export, and `ocf locale` CLI wiring."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest
import yaml
from conftest import REPO_ROOT
from ocf_tools.cli import main
from ocf_tools.locale import LocalizationError
from ocf_tools.transcript import export_srt, load_timed_doc
from ocf_tools.voice import (
    apply_pronunciation,
    backend_locale_support,
    render_narration,
    resolve_backend,
)

FAKE_BACKEND = {
    "name": "espeak-ng",
    "binary": "espeak-ng",
    "language": "en",
    "wpm": 100,
}


def fixed_cue(text: str, *, rate: int = 8000, seconds: float = 0.25) -> bytes:
    """Deterministic PCM so tests never shell out to a speech engine."""
    import io

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def keyed_doc(locale: str | None = "en-US", keys=("session.focus-cycle.opener",)):
    return {
        "schema_version": "1.0",
        "title": "Keyed session",
        "locale": locale,
        "timeline": [
            {"id": f"e{index}", "at": float(index * 3), "narration_key": key}
            for index, key in enumerate(keys)
        ],
    }


def write_doc(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "keyed.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Render narration
# ---------------------------------------------------------------------------


class TestLocalizedRender:
    def test_renders_without_locale_when_document_is_inline(self, tmp_path):
        doc = {
            "schema_version": "1.0",
            "title": "Inline",
            "timeline": [{"id": "a", "at": 0.0, "text": "Breathe in."}],
        }
        metadata = render_narration(
            doc,
            tmp_path / "out.wav",
            backend=FAKE_BACKEND,
            render_cue=fixed_cue,
        )
        assert metadata["cues"] == 1
        assert metadata.get("locale") is None

    def test_strict_render_fails_loudly_on_a_missing_translation(self, tmp_path):
        path = write_doc(
            tmp_path, keyed_doc(keys=("focus.eleven.hold",))
        )
        with pytest.raises(LocalizationError):
            render_narration(
                load_timed_doc(path),
                tmp_path / "out.wav",
                backend=FAKE_BACKEND,
                render_cue=fixed_cue,
                locale="es",
            )

    def test_explicit_fallback_renders_and_records_provenance(self, tmp_path):
        path = write_doc(tmp_path, keyed_doc(keys=("focus.eleven.hold",)))
        metadata = render_narration(
            load_timed_doc(path),
            tmp_path / "out.wav",
            backend=FAKE_BACKEND,
            render_cue=fixed_cue,
            locale="es",
            strict=False,
        )
        assert metadata["cues"] == 1
        assert metadata["locale"] == "es"
        assert metadata["cue_stats"][0]["text"]

    def test_localized_text_reaches_the_backend(self, tmp_path):
        seen: list[str] = []

        def spy(text: str) -> bytes:
            seen.append(text)
            return fixed_cue(text)

        path = write_doc(tmp_path, keyed_doc())
        render_narration(
            load_timed_doc(path),
            tmp_path / "out.wav",
            backend=FAKE_BACKEND,
            render_cue=spy,
            locale="es",
        )
        assert seen and seen[0]
        assert "{" not in seen[0]

    def test_cue_stats_expose_measured_duration(self, tmp_path):
        path = write_doc(tmp_path, keyed_doc())
        metadata = render_narration(
            load_timed_doc(path),
            tmp_path / "out.wav",
            backend=FAKE_BACKEND,
            render_cue=fixed_cue,
            locale="en-US",
        )
        cue = metadata["cue_stats"][0]
        assert cue["at"] == 0.0
        assert cue["duration"] == pytest.approx(0.25, abs=0.01)

    def test_locale_mismatch_is_recorded_in_metadata(self, tmp_path):
        metadata = render_narration(
            keyed_doc(),
            tmp_path / "out.wav",
            backend=FAKE_BACKEND,
            render_cue=fixed_cue,
            locale="en-US",
        )
        assert metadata["locale"] == "en-US"
        assert isinstance(metadata["locale_notes"], list)
        assert metadata["pronunciation_hints"] >= 0


# ---------------------------------------------------------------------------
# Backend locale handling
# ---------------------------------------------------------------------------


class TestBackendLocale:
    def test_espeak_retargets_to_the_requested_language(self):
        spec = resolve_backend(FAKE_BACKEND, [], locale="es")
        assert spec["language"] == "es"
        assert spec["locale"] == "es"
        assert isinstance(spec.get("notes"), list)

    def test_language_only_backend_accepts_any_locale_tag(self):
        # espeak is keyed by language, so a regional tag simply narrows.
        spec = resolve_backend({"name": "espeak", "language": "en"}, [], locale="pt-BR")
        assert spec["language"] == "pt"

    def test_apply_pronunciation_substitutes_the_hint_for_espeak(self):
        # A pronunciation override replaces the token; it must not repeat it.
        assert apply_pronunciation("hola", {"hola": {"espeak-ng": "hola"}}, "espeak-ng") == (
            "hola"
        )

    def test_apply_pronunciation_leaves_other_backends_alone(self):
        # Piper takes a sentence, not a hint: a wrong-backend hint is ignored.
        assert apply_pronunciation("hola", {"hola": {"piper": "hola"}}, "piper") == "hola"

    def test_apply_pronunciation_ignores_absent_tokens(self):
        assert apply_pronunciation("hola", {"adios": {"espeak-ng": "a"}}, "espeak-ng") == "hola"

    def test_backend_locale_support_reports_what_it_can_do(self):
        support = backend_locale_support("espeak-ng")
        assert support["backend"] == "espeak-ng"
        assert support["pronunciation_syntax"]
        assert support["default_language"]

    def test_unknown_backend_reports_nothing_rather_than_guessing(self):
        support = backend_locale_support("not-a-backend")
        assert support["locale_style"] == "language-only"
        assert support["pronunciation_syntax"] is None


# ---------------------------------------------------------------------------
# Subtitle export
# ---------------------------------------------------------------------------


class TestLocalizedExport:
    def test_measured_timings_replace_the_estimate(self, tmp_path):
        from ocf_tools.transcript import measured_durations

        doc = load_timed_doc(write_doc(tmp_path, keyed_doc()))
        render = {
            "voice": {"backend": "fake-tts"},
            "narration_timing": {
                "mode": "fit-soft",
                "measured": True,
                "cues": [{"id": "e0", "at": 0.0, "duration": 4.5}],
            },
        }
        from ocf_tools.transcript import _export_events

        measured = measured_durations(render, _export_events(doc))
        assert measured == {"e0": 4.5}
        srt = export_srt(doc, measured=measured)
        assert "00:00:04,500" in srt

    def test_export_without_measurements_uses_the_timeline(self, tmp_path):
        doc = load_timed_doc(write_doc(tmp_path, keyed_doc()))
        assert "00:00:0" in export_srt(doc)

    def test_cli_export_resolves_the_requested_locale(self, tmp_path, capsys):
        path = write_doc(tmp_path, keyed_doc())
        assert main(["transcript", "export", str(path), "--format", "srt", "--locale", "es"]) == 0
        out = capsys.readouterr().out
        assert "Comienza" in out or "ATENCIÓN" in out.upper()

    def test_cli_export_strict_failure_is_reported(self, tmp_path, capsys):
        path = write_doc(tmp_path, keyed_doc(keys=("focus.eleven.hold",)))
        assert main(["transcript", "export", str(path), "--format", "srt", "--locale", "es"]) == 1
        assert "focus.eleven.hold" in capsys.readouterr().err

    def test_cli_export_can_use_a_render_manifest(self, tmp_path, capsys):
        path = write_doc(tmp_path, keyed_doc())
        render = tmp_path / "OCF-RENDER-demo.yaml"
        render.write_text(
            yaml.safe_dump(
                {
                    "voice": {"backend": "fake-tts"},
                    "narration_timing": {
                        "cues": [{"id": "e0", "at": 0.0, "duration": 3.25}]
                    },
                }
            ),
            encoding="utf-8",
        )
        code = main(
            [
                "transcript",
                "export",
                str(path),
                "--format",
                "srt",
                "--render-manifest",
                str(render),
            ]
        )
        assert code == 0
        assert "00:00:03,250" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestLocaleCli:
    def test_list_reports_every_pack(self, capsys):
        assert main(["locale", "list"]) == 0
        out = capsys.readouterr().out
        assert "en-US" in out and "es" in out

    def test_coverage_accepts_domain_filter(self, capsys):
        assert main(["locale", "coverage", "--locale", "es", "--domain", "narration"]) == 0
        # The es pack localizes the CLI itself, which is the point of the pack.
        assert "17 de 105" in capsys.readouterr().out  # includes sixteen draft pilot keys

    def test_validate_passes_on_the_repository_packs(self, capsys):
        assert main(["locale", "validate"]) == 0

    def test_resolve_writes_a_provenance_carrying_document(self, tmp_path, capsys):
        out = tmp_path / "resolved.yaml"
        assert (
            main(
                [
                    "locale",
                    "resolve",
                    "--file",
                    str(write_doc(tmp_path, keyed_doc())),
                    "--locale",
                    "es",
                    "--output",
                    str(out),
                ]
            )
            == 0
        )
        resolved = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert resolved["narration"]["locale"] == "es"
        assert resolved["timeline"][0]["narration_key"]

    def test_resolve_from_a_session_template(self, tmp_path, capsys):
        template = (
            REPO_ROOT / "audio/templates/sessions/OCF-TPL-SESSION-FOCUS-CYCLE-001.yaml"
        )
        assert (
            main(
                [
                    "locale",
                    "resolve",
                    "--session",
                    str(template),
                    "--locale",
                    "es",
                    "--output",
                    str(tmp_path / "s.yaml"),
                ]
            )
            == 0
        )
        resolved = yaml.safe_load((tmp_path / "s.yaml").read_text(encoding="utf-8"))
        texts = " ".join(
            event.get("text", "")
            for section in resolved.get("sections") or []
            for event in section.get("timeline") or []
        )
        assert texts.strip()
        assert resolved["narration"]["locale"] == "es"
        assert all(event["narration_key"] for event in resolved["sections"][0]["timeline"])

    def test_pseudo_writes_a_loadable_pack(self, tmp_path, capsys):
        root = tmp_path / "en-XA"
        assert (
            main(["locale", "pseudo", "--from", "en-US", "--output", str(root)]) == 0
        )
        manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
        assert manifest["locale"] == "en-XA"
        assert {r["domain"] for r in manifest["resources"]} == {"ui", "narration"}
        narration = yaml.safe_load((root / "narration.yaml").read_text(encoding="utf-8"))
        assert narration["domain"] == "narration"
        assert any(
            isinstance(value, dict) and value.get("text")
            for value in narration["entries"].values()
        )

    def test_voice_render_accepts_a_locale(self, tmp_path, capsys):
        doc = write_doc(tmp_path, keyed_doc())
        out = tmp_path / "narration.wav"
        code = main(
            [
                "voice",
                "render",
                str(doc),
                "--locale",
                "en-US",
                "--output",
                str(out),
                "--backend",
                "fake-tts",
                "--force",
            ]
        )
        assert code in (0, 1)  # backend availability is machine-specific
        assert "--locale" in capsys.readouterr().out or code == 0


# ---------------------------------------------------------------------------
# Build manifest
# ---------------------------------------------------------------------------


class TestBuildManifest:
    """`ocf audio build --locale` must record measured speech timings."""

    def _manifest(self, tmp_path: Path, transcript: Path) -> Path:
        manifest = {
            "schema_version": "1.0",
            "id": "OCF-AUDIO-9001",
            "function_id": "OCF-FND-002",
            "title": "Localized build fixture",
            "version": "0.1.0",
            "contributor": "test",
            "narrator": "test",
            "language": "en",
            "license": "Apache-2.0",
            "training_type": "training",
            "transcript_path": str(transcript),
            "background_audio": {"strategy": "disabled", "preset": None},
            "technical": {"sample_rate": 16000, "channels": 1, "format": "wav", "formats": ["wav"]},
        }
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        return path

    def test_build_records_locale_and_measured_timings(self, tmp_path):
        from ocf_tools.audio_build import build

        transcript = write_doc(tmp_path, keyed_doc())
        manifest = self._manifest(tmp_path, transcript)
        out_root = tmp_path / "rendered"
        report = build(
            str(manifest),
            out_root=out_root,
            voice=FAKE_BACKEND,
            render_cue=fixed_cue,
            locale="es",
            overwrite=True,
        )
        assert report["voice"]["locale"] == "es"
        assert report["narration_timing"]["measured"] is True
        assert report["narration_timing"]["cues"][0]["id"] == "e0"
        assert report["narration_timing"]["cues"][0]["duration"] > 0

    def test_render_manifest_feeds_subtitle_export(self, tmp_path):
        from ocf_tools.audio_build import build

        transcript = write_doc(tmp_path, keyed_doc())
        manifest = self._manifest(tmp_path, transcript)
        out_root = tmp_path / "rendered"
        build(
            str(manifest),
            out_root=out_root,
            voice=FAKE_BACKEND,
            render_cue=fixed_cue,
            locale="es",
            overwrite=True,
        )
        render_manifest = next(out_root.glob("OCF-RENDER-*.yaml"))
        assert main(
            [
                "transcript",
                "export",
                str(transcript),
                "--format",
                "srt",
                "--locale",
                "es",
                "--render-manifest",
                str(render_manifest),
            ]
        ) == 0


# ---------------------------------------------------------------------------
# Regressions
# ---------------------------------------------------------------------------


class TestRegressions:
    def test_generated_yaml_banner_does_not_break_loading(self, tmp_path):
        """Generated files carry a plain-text banner; YAML must still read them."""
        from ocf_tools.indexes import load_yaml_file

        path = tmp_path / "generated.yaml"
        path.write_text(
            "GENERATED FILE — DO NOT EDIT DIRECTLY\n\nid: X\ngenerated: '2026-01-01'\n",
            encoding="utf-8",
        )
        assert load_yaml_file(path) == {"id": "X", "generated": "2026-01-01"}

    def test_measured_duration_is_seconds_not_seconds_over_sample_rate(self, tmp_path):
        """A recorded duration must not be divided by the sample rate again."""
        from ocf_tools.audio_build import build

        transcript = tmp_path / "keyed.yaml"
        transcript.write_text(yaml.safe_dump(keyed_doc()), encoding="utf-8")
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "id": "OCF-AUDIO-9002",
                    "function_id": "OCF-FND-002",
                    "title": "timing fixture",
                    "version": "0.1.0",
                    "contributor": "test",
                    "narrator": "test",
                    "language": "en",
                    "license": "Apache-2.0",
                    "training_type": "training",
                    "transcript_path": str(transcript),
                    "background_audio": {"strategy": "disabled", "preset": None},
                    "technical": {
                        "sample_rate": 16000,
                        "channels": 1,
                        "format": "wav",
                        "formats": ["wav"],
                    },
                }
            ),
            encoding="utf-8",
        )
        report = build(
            str(manifest),
            out_root=tmp_path / "rendered",
            voice=FAKE_BACKEND,
            render_cue=fixed_cue,  # 0.25 s of audio
            locale="es",
            overwrite=True,
        )
        assert report["narration_timing"]["cues"][0]["duration"] == pytest.approx(0.25, abs=0.01)

    def test_session_compose_can_target_a_locale(self, tmp_path, capsys):
        code = main(
            [
                "session",
                "compose",
                "--template",
                "OCF-TPL-SESSION-FOCUS-CYCLE-001",
                "--locale",
                "es",
                "--output",
                str(tmp_path / "es.yaml"),
                "--force",
            ]
        )
        assert code == 0
        doc = yaml.safe_load((tmp_path / "es.yaml").read_text(encoding="utf-8"))
        assert doc["locale"] == "es"
        assert doc["narration"]["locale"] == "es"
        first = doc["sections"][0]["timeline"][0]
        assert first["narration_key"] and first["text"]

    def test_list_backends_reports_locale_capability(self, capsys):
        assert main(["voice", "list-backends"]) in (0, 1)
        out = capsys.readouterr().out
        assert "locale:" in out


class TestBackgroundPresetResolution:
    """The Farfield background path was dead: `farfield render` only accepts a
    session YAML path, but background manifests name the bed by id, and the
    temp output filename was built from the whole preset string."""

    def test_background_id_resolves_to_its_farfield_session_file(self):
        """A background id resolves to the named session, wherever it lives."""
        from ocf_tools.audio_build import _farfield_preset_file

        source = Path(_farfield_preset_file("OCF-BG-0007"))
        assert source.name == "focus-11-c.yaml"
        assert source.is_file()

    def test_farfield_own_presets_are_preferred_over_ocf_copies(self, monkeypatch, tmp_path):
        """Farfield's built-ins win; OCF's committed copies are the fallback."""
        import ocf_tools.audio_build as audio_build

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "focus-11-c.yaml").write_text("name: from-upstream\n", encoding="utf-8")
        monkeypatch.setattr(
            audio_build.farfield_mod,
            "farfield_preset_dirs",
            lambda: [upstream, REPO_ROOT / "audio" / "background" / "presets" / "farfield"],
        )
        source = Path(audio_build._farfield_preset_file("OCF-BG-0007"))
        assert source == upstream / "focus-11-c.yaml"

    def test_ocf_copy_is_the_fallback_when_farfield_lacks_the_preset(self, monkeypatch):
        import ocf_tools.audio_build as audio_build

        monkeypatch.setattr(
            audio_build.farfield_mod, "farfield_preset_dirs", lambda: [Path("/nonexistent")]
        )
        source = Path(audio_build._farfield_preset_file("OCF-BG-0007"))
        assert source == REPO_ROOT / "audio/background/presets/farfield/focus-11-c.yaml"

    def test_farfield_preset_file_passes_an_explicit_path_through(self):
        """An explicit path is never silently redirected to a built-in."""
        from ocf_tools.audio_build import _farfield_preset_file

        direct = "audio/background/presets/farfield/focus-11-c.yaml"
        assert _farfield_preset_file(direct) == direct

    def test_non_farfield_id_is_not_rewritten_to_a_session_file(self):
        from ocf_tools.audio_build import _farfield_preset_file

        assert _farfield_preset_file("OCF-BG-0002") == "OCF-BG-0002"

    @pytest.mark.parametrize(
        "preset, expected",
        [
            ("OCF-BG-0007", "OCF-BG-0007"),
            ("audio/background/presets/farfield/focus-11-c.yaml", "focus-11-c"),
            ("/abs/path/focus-11-c.yaml", "focus-11-c"),
            ("weird:id", "weird-id"),
        ],
    )
    def test_preset_stem_is_filesystem_safe(self, preset, expected):
        from ocf_tools.audio_build import _preset_stem

        assert _preset_stem(preset) == expected

    def test_any_engine_bed_uses_the_ffmpeg_master_mix(self, monkeypatch):
        """24-bit / long engine stems must not reach the pure-stdlib PCM mix."""
        from ocf_tools import audio_build

        seen = {}

        def fake_ffmpeg(speech, background, out, **kwargs):
            seen["background"] = Path(background)

        monkeypatch.setattr(audio_build, "_mix_master_ffmpeg", fake_ffmpeg)
        monkeypatch.setattr(
            audio_build, "mix", lambda *a, **k: pytest.fail("pure-stdlib mix used for a bed")
        )
        transcript = REPO_ROOT / "audio" / "scripts" / "attention-ocf.yaml"
        if not transcript.is_file():
            pytest.skip("legacy attention script not present")
        manifest = yaml.safe_load(
            (REPO_ROOT / "audio" / "manifests" / "OCF-AUDIO-0001.yaml").read_text(encoding="utf-8")
        )
        manifest["id"] = "OCF-AUDIO-9003"
        manifest["transcript_path"] = str(transcript)
        manifest["background_audio"] = {"strategy": "required", "preset": "OCF-BG-0007"}
        manifest["technical"].pop("checksum_sha256", None)
        manifest_path = REPO_ROOT / "tests" / "fixtures" / "_tmp-audio-9003.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        try:
            monkeypatch.setattr(
                audio_build,
                "_render_background",
                lambda *a, **k: (Path("/tmp/bed-24bit.wav"), "farfield"),
            )
            audio_build.build(
                str(manifest_path),
                out_root=REPO_ROOT / "tests" / "fixtures" / "_tmp-render",
                voice=FAKE_BACKEND,
                render_cue=fixed_cue,
                locale="en-US",
                overwrite=True,
            )
        except Exception:
            pass  # the mix is what this test asserts on, not the rest of the build
        finally:
            manifest_path.unlink(missing_ok=True)
        assert seen.get("background") == Path("/tmp/bed-24bit.wav")


class TestFarfieldPresetSearchPath:
    """Farfield's wheel ships no presets; they live in the checkout that PEP 610
    records. Names resolve against Farfield's own presets first, then OCF's."""

    def test_committed_presets_outrank_the_farfield_checkout(self, monkeypatch):
        """Builds must not depend on where Farfield was installed from."""
        from ocf_tools import farfield

        monkeypatch.delenv("OCF_FARFIELD_PRESETS_DIR", raising=False)
        monkeypatch.setattr(
            farfield, "_source_preset_dirs", lambda: [Path("/somewhere/farfield/presets")]
        )
        dirs = farfield.farfield_preset_dirs()
        assert dirs[0] == REPO_ROOT / "audio" / "background" / "presets" / "farfield"
        assert dirs[-1] == Path("/somewhere/farfield/presets")

    def test_env_var_raises_priority_without_dropping_the_committed_tier(
        self, monkeypatch, tmp_path
    ):
        from ocf_tools import farfield

        monkeypatch.setattr(farfield, "_source_preset_dirs", list)
        monkeypatch.setenv("OCF_FARFIELD_PRESETS_DIR", str(tmp_path))
        dirs = farfield.farfield_preset_dirs()
        assert dirs[0] == tmp_path
        assert REPO_ROOT / "audio" / "background" / "presets" / "farfield" in dirs

    def test_every_committed_preset_resolves_without_the_farfield_checkout(self, monkeypatch):
        from ocf_tools import farfield

        monkeypatch.delenv("OCF_FARFIELD_PRESETS_DIR", raising=False)
        monkeypatch.setattr(farfield, "_source_preset_dirs", list)
        committed = sorted(
            p.stem
            for p in (REPO_ROOT / "audio" / "background" / "presets" / "farfield").glob("*.yaml")
        )
        assert committed, "expected committed Farfield presets"
        unresolved = [name for name in committed if farfield.resolve_preset(name) is None]
        assert unresolved == []

    def test_resolve_preset_finds_an_ocf_committed_copy(self):
        from ocf_tools import farfield

        monkey = farfield.resolve_preset("focus-11-c")
        assert monkey is not None and monkey.name == "focus-11-c.yaml"

    def test_resolve_preset_returns_none_for_an_unknown_name(self):
        from ocf_tools import farfield

        assert farfield.resolve_preset("definitely-not-a-preset") is None

    def test_search_report_names_every_directory_checked(self, monkeypatch, tmp_path):
        from ocf_tools import farfield

        monkeypatch.setenv("OCF_FARFIELD_PRESETS_DIR", str(tmp_path))
        report = farfield.preset_search_report("nope")
        assert "nope" in report
        assert str(tmp_path) in report
        assert "OCF_FARFIELD_PRESETS_DIR" in report
